"""Backend API Akun Trading (MT4/MT5) — READ-ONLY.

Menyajikan:
  - Frontend statis dari root repo (index.html kalkulator TIDAK diubah;
    backend/ dan data/ TIDAK dilayani ke publik)
  - API /api/trading/* untuk koneksi, status, statistik, riwayat

Keamanan:
  - Password dienkripsi di simpanan (Fernet), tidak pernah muncul di
    request/response/log.
  - Token API opsional via TRADING_API_TOKEN (header Authorization: Bearer).
  - Tidak ada endpoint eksekusi order — statistik & riwayat saja.
Jalankan:  python backend/app.py  → http://127.0.0.1:5000
"""
from __future__ import annotations

import threading
import time
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory

from connectors.base import Connector, ConnectorError, ConnectorUnavailable
from connectors.demo import DemoConnector
from connectors.mt4_pytrader import MT4PyTraderConnector
from connectors.mt5_api import MT5Connector
from services.store import AccountStore, StoreError
from services import stats as stats_svc
import config

app = Flask(__name__, static_folder=None)

store = AccountStore()
_reg_lock = threading.Lock()
_connectors: dict[str, Connector] = {}


# ---------------------------------------------------------------- utilitas
def err(code: str, message: str, http: int):
    return jsonify({"error": {"code": code, "message": message}}), http


def _active_connector() -> Connector:
    acc_id = store.active_id()
    if not acc_id:
        raise ConnectorError("Belum ada akun yang terhubung.")
    conn = _connectors.get(acc_id)
    if conn is None or not conn.is_connected():
        raise ConnectorError("Akun aktif belum terhubung. Tekan Hubungkan dulu.")
    return conn


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if config.API_TOKEN:
            header = request.headers.get("Authorization", "")
            if header != f"Bearer {config.API_TOKEN}":
                return err("UNAUTHORIZED",
                           "Token API tidak valid atau tidak ada.", 401)
        return fn(*args, **kwargs)
    return wrapper


@app.after_request
def security_headers(resp):
    if config.CORS_ENABLED:
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# ------------------------------------------------------------ statis
@app.get("/")
def home():
    return send_from_directory(config.PROJECT_ROOT, "index.html")


@app.get("/<path:fname>")
def static_files(fname: str):
    # Larang akses kode backend, data tersimpan, dan endpoint API dari route statis
    if fname.startswith("backend/") or fname.startswith("api/") or fname.startswith("."):
        return err("FORBIDDEN", "Path ini tidak dilayani.", 404)
    allowed = ("index.html", "trading.html", "style.css", "script.js",
               "trading.css", "trading.js", "README.md")
    if fname not in allowed:
        return err("FORBIDDEN", "Path ini tidak dilayani.", 404)
    return send_from_directory(config.PROJECT_ROOT, fname)


@app.route("/<path:fname>", methods=["POST", "PUT", "DELETE", "PATCH"])
def static_write_block(fname: str):
    # Semua penulisan via web tidak dilayani (backend read-only)
    return err("FORBIDDEN", "Path ini tidak dilayani.", 404)


# ------------------------------------------------------------ API
@app.get("/api/trading/health")
def health():
    mt5_ok = True
    try:
        import importlib
        importlib.import_module("MetaTrader5")
    except ImportError:
        mt5_ok = False
    return jsonify({
        "ok": True, "service": "trading-account",
        "connectors": {"mt5_available": mt5_ok, "mt4_available": True,
                       "demo_available": True},
        "auth_required": bool(config.API_TOKEN),
        "persistent_encryption": store.persistent_encryption,
        "time": int(time.time()),
    })


def _validate_account_payload(d: dict) -> dict:
    platform = str(d.get("platform", "")).strip().lower()
    if platform not in ("mt5", "mt4", "demo"):
        raise ValueError("Platform harus mt5, mt4, atau demo.")
    out: dict = {"platform": platform}
    if platform == "demo":
        out["login"] = str(d.get("login", "")).strip()[:40]  # dipakai sebagai seed
        out["password"] = ""
        out["server"] = ""
        out["extra"] = {}
    if platform in ("mt5", "mt4"):
        login = str(d.get("login", "")).strip()
        if not login or not login.isdigit():
            raise ValueError("Nomor login harus berupa angka.")
        out["login"] = login
        out["password"] = str(d.get("password", ""))
        if platform == "mt5" and not out["password"]:
            raise ValueError("Password akun MT5 wajib diisi.")
        out["server"] = str(d.get("server", "")).strip()
        if not out["server"]:
            raise ValueError("Nama server broker wajib diisi.")
        extra = {}
        if platform == "mt4":
            host = str(d.get("bridge_host", "")).strip()
            if not host:
                raise ValueError(
                    "Alamat bridge MT4 (host/IP komputer terminal) wajib diisi.")
            extra["bridge_host"] = host
            try:
                extra["bridge_port"] = int(d.get("bridge_port") or 2345)
            except (TypeError, ValueError):
                raise ValueError("Port bridge harus angka.")
        out["extra"] = extra
    out["label"] = str(d.get("label", "")).strip()[:60]
    return out


def _build_connector(acc: dict) -> Connector:
    p = acc["platform"]
    if p == "demo":
        return DemoConnector(seed=acc["login"] or acc["id"])
    if p == "mt5":
        return MT5Connector(login=acc["login"],
                            password=store.decrypt_password(acc["id"]),
                            server=acc["server"],
                            terminal_path=config.MT5_TERMINAL_PATH)
    if p == "mt4":
        extra = acc.get("extra", {})
        return MT4PyTraderConnector(
            server_host=extra.get("bridge_host", ""),
            port=int(extra.get("bridge_port", 2345)),
            auth_code=str(acc.get("extra", {}).get("auth_code", "None")))
    raise ConnectorError("Platform tidak dikenal.")


@app.post("/api/trading/accounts")
@require_auth
def create_account():
    d = _json_body()
    try:
        v = _validate_account_payload(d)
    except ValueError as e:
        return err("VALIDATION", str(e), 400)
    try:
        acc = store.add(**v, max_accounts=config.MAX_ACCOUNTS)
    except StoreError as e:
        return err("STORE", str(e), 400)
    return jsonify({"account": acc}), 201


@app.get("/api/trading/accounts")
@require_auth
def list_accounts():
    return jsonify({"accounts": store.list(), "active": store.active_id()})


@app.delete("/api/trading/accounts/<account_id>")
@require_auth
def delete_account(account_id: str):
    try:
        with _reg_lock:
            conn = _connectors.pop(account_id, None)
            if conn:
                conn.disconnect()
        store.delete(account_id)
    except StoreError as e:
        return err("STORE", str(e), 404)
    return jsonify({"ok": True})


@app.post("/api/trading/connect")
@require_auth
def connect():
    d = _json_body()
    account_id = str(d.get("account_id", "")).strip()
    acc = store.get(account_id)
    if not acc:
        return err("NOT_FOUND", "Akun tidak ditemukan.", 404)
    try:
        conn = _build_connector(acc)
        info = conn.connect()
    except ConnectorUnavailable as e:
        return err("CONNECTOR_UNAVAILABLE", str(e), 503)
    except ConnectorError as e:
        return err("CONNECT", str(e), 502)
    with _reg_lock:
        _connectors[account_id] = conn
    try:
        store.set_active(account_id)
    except StoreError:
        pass
    return jsonify({"connected": True, "mode": conn.mode,
                    "platform": conn.platform, "account": info})


@app.post("/api/trading/disconnect")
@require_auth
def disconnect():
    acc_id = store.active_id()
    with _reg_lock:
        conn = _connectors.pop(acc_id, None) if acc_id else None
        if conn:
            conn.disconnect()
    return jsonify({"connected": False})


@app.get("/api/trading/status")
@require_auth
def status():
    acc_id = store.active_id()
    conn = _connectors.get(acc_id) if acc_id else None
    if not conn or not conn.is_connected():
        return jsonify({"connected": False, "account": None, "mode": None})
    try:
        snap = conn.snapshot()
    except ConnectorError as e:
        return err("CONNECT", str(e), 502)
    acc = store.get(acc_id)
    base = conn.connect() if hasattr(conn, "connect") else {}
    info = {**base, **snap}
    return jsonify({"connected": True, "account_id": acc_id,
                    "mode": conn.mode, "platform": conn.platform,
                    "label": (acc or {}).get("label"), "account": info})


def _period_args():
    d = request.args
    period = d.get("period", "all")
    try:
        from_ts = int(float(d.get("from", 0) or 0))
        to_ts = int(float(d.get("to", 0) or 0))
        since, until = stats_svc.resolve_period(period, from_ts, to_ts)
    except ValueError as e:
        raise ValueError(str(e))
    return since, until, period


def _fetch_data(conn: Connector, since: int, until: int):
    deals = conn.closed_positions(since, until)
    deposits = conn.balance_operations(since, until)
    return deals, deposits


@app.get("/api/trading/summary")
@require_auth
def summary():
    try:
        conn = _active_connector()
        since, until, period = _period_args()
        deals, deposits = _fetch_data(conn, since, until)
        snap = conn.snapshot()
        data = stats_svc.compute_summary(deals, deposits,
                                         floating=snap["floating"],
                                         balance=snap["balance"],
                                         equity=snap["equity"])
        data["period"] = period
        data["mode"] = conn.mode
        data["notes"] = [
            "Profit bersih = profit + swap + komisi per posisi tertutup.",
            "Drawdown dihitung dari kurva balance trade tertutup, bukan tick-per-tick.",
        ]
        if not data["deposits_available"]:
            data["notes"].append(
                "Sumber data tidak menyediakan riwayat deposit/withdrawal "
                "(mis. bridge MT4). Kolom deposit ditandai tidak tersedia.")
        return jsonify(data)
    except ValueError as e:
        return err("VALIDATION", str(e), 400)
    except ConnectorError as e:
        return err("CONNECT", str(e), 502)


@app.get("/api/trading/history")
@require_auth
def history():
    try:
        conn = _active_connector()
        since, until, period = _period_args()
        deals = conn.closed_positions(since, until)
        deals.sort(key=lambda x: x.get("close_time") or 0, reverse=True)
        try:
            limit = max(1, min(500, int(request.args.get("limit", 100))))
        except ValueError:
            limit = 100
        try:
            offset = max(0, int(request.args.get("offset", 0)))
        except ValueError:
            offset = 0
        return jsonify({"total": len(deals),
                        "deals": deals[offset:offset + limit],
                        "mode": conn.mode, "period": period})
    except ValueError as e:
        return err("VALIDATION", str(e), 400)
    except ConnectorError as e:
        return err("CONNECT", str(e), 502)


@app.get("/api/trading/curve")
@require_auth
def curve():
    try:
        conn = _active_connector()
        since, until, period = _period_args()
        deals, deposits = _fetch_data(conn, since, until)
        return jsonify({"points": stats_svc.equity_curve(deals, deposits),
                        "mode": conn.mode, "period": period})
    except ValueError as e:
        return err("VALIDATION", str(e), 400)
    except ConnectorError as e:
        return err("CONNECT", str(e), 502)


@app.errorhandler(404)
def not_found(_):
    return err("NOT_FOUND", "Endpoint tidak ditemukan.", 404)


@app.errorhandler(500)
def internal(_):
    return err("INTERNAL", "Kesalahan internal backend.", 500)


if __name__ == "__main__":
    print(" * Akun Trading backend aktif di http://127.0.0.1:5000")
    print("   Kalkulator lama : http://127.0.0.1:5000/  (tidak berubah)")
    print("   Dashboard       : http://127.0.0.1:5000/trading.html")
    if not store.persistent_encryption:
        print("   ! PERINGATAN: TRADING_SECRET_KEY belum diset — kunci enkripsi")
        print("     acak per proses; password tersimpan tak terbaca setelah restart.")
    if not config.API_TOKEN:
        print("   ! TRADING_API_TOKEN belum diset — API tanpa autentikasi (lokal saja).")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
