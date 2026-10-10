"""Konektor MT4 memakai protokol PyTrader (TheSnowGuru/PyTrader-...).

Cara kerja: EA PyTrader berjalan di dalam terminal MT4 (Windows/Wine) dan
membuka server TCP (default port 2345). Klien mengirim perintah teks dengan
format  PERINTAH^param^<auth_code>^!  dan membaca balasan sampai terminator '!'.

Perintah yang dipakai (read-only):
  F001^1^   -> info akun statis (nama, login, currency, leverage, company)
  F002^1^   -> info akun dinamis (balance, equity, profit, margin)
  F061^1^   -> semua posisi terbuka
  F062^<dari>^<sampai>^ -> posisi tertutup dalam rentang waktu

Catatan jujur: nama/format field bisa sedikit berbeda antar versi EA
(V3.02c vs V4.01). Field mapping ada di _parse_closed/_parse_open dan mudah
disesuaikan. Koneksi MT4 TIDAK butuh password broker — autentikasi ke EA
memakai authorization_code (opsional, diset di EA).
"""
from __future__ import annotations

import socket
import time
from typing import Optional

from .base import Connector, ConnectorError

DEFAULT_PORT = 2345
DEFAULT_TIMEOUT = 10.0
DATE_FMT = "%Y.%m.%d %H:%M"


class MT4PyTraderConnector(Connector):
    platform = "mt4"
    mode = "live"

    def __init__(self, server_host: str, port: int = DEFAULT_PORT,
                 auth_code: str = "None", timeout: float = DEFAULT_TIMEOUT):
        if not server_host:
            raise ConnectorError(
                "Alamat host bridge MT4 (IP komputer tempat terminal MT4 + "
                "EA PyTrader berjalan) wajib diisi."
            )
        self._host = str(server_host).strip()
        self._port = int(port)
        self._auth = auth_code or "None"
        self._timeout = float(timeout)
        self._sock: Optional[socket.socket] = None
        self._static: Optional[dict] = None

    # ---- protokol socket ------------------------------------------------
    def _send(self, command: str) -> str:
        if self._sock is None:
            raise ConnectorError("Belum terhubung ke bridge MT4.")
        payload = f"{command}{self._auth}^!"
        try:
            self._sock.sendall(payload.encode("utf-8"))
            buf = ""
            deadline = time.time() + self._timeout
            while time.time() < deadline:
                chunk = self._sock.recv(500000)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", errors="replace")
                if buf.rstrip().endswith("!"):
                    return buf.rstrip().rstrip("!")
            raise ConnectorError("Bridge MT4 tidak membalas (timeout). "
                                 "Pastikan EA PyTrader aktif di terminal.")
        except socket.error as e:
            self._connected_false()
            raise ConnectorError(
                f"Koneksi ke bridge MT4 terputus ({e.__class__.__name__}). "
                "Periksa IP/port dan firewall."
            )

    def _connected_false(self):
        try:
            if self._sock:
                self._sock.close()
        finally:
            self._sock = None

    # ---- siklus hidup ---------------------------------------------------
    def connect(self) -> dict:
        try:
            self._sock = socket.create_connection((self._host, self._port),
                                                  timeout=self._timeout)
        except OSError:
            raise ConnectorError(
                f"Tidak bisa terhubung ke bridge MT4 di {self._host}:{self._port}. "
                "Pastikan terminal MT4 dengan EA PyTrader berjalan dan port "
                "dibuka di firewall (lihat docs/MT4-MT5-FITUR.md)."
            )
        try:
            self._static = self._parse_static(self._send("F001^1^"))
            self._static["platform"] = self.platform
            self._static.setdefault("server", self._host)
            return self._static
        except ConnectorError:
            self.disconnect()
            raise

    def disconnect(self) -> None:
        self._connected_false()

    def is_connected(self) -> bool:
        return self._sock is not None

    # ---- parser respons ---------------------------------------------------
    @staticmethod
    def _records(resp: str, cmd: str) -> list[str]:
        parts = resp.split("^")
        if not parts or parts[0] != cmd:
            raise ConnectorError(
                "Balasan bridge MT4 tidak dikenali (mungkin versi EA berbeda).")
        del parts[0:2]
        if parts and parts[-1] == "":
            parts.pop()
        return parts

    def _parse_static(self, resp: str) -> dict:
        r = self._records(resp, "F001")
        # V4.01: name,login,currency,type,leverage,trade_allowed,limit_orders,margin_call,margin_close,company
        f = r[0].split("$") if r else []
        if len(f) < 10:
            raise ConnectorError("Format info akun MT4 tidak sesuai harapan.")
        return {"name": f[0], "login": f[1], "currency": f[2],
                "broker": f[9], "leverage": int(float(f[4]))}

    def dynamic_info(self) -> dict:
        r = self._records(self._send("F002^1^"), "F002")
        f = r[0].split("$") if r else []
        if len(f) < 3:
            raise ConnectorError("Format info dinamis MT4 tidak sesuai harapan.")
        return {"balance": float(f[0]), "equity": float(f[1])}

    @staticmethod
    def _parse_closed(rec: str) -> dict:
        y = rec.split("$")
        # V4.01 closed: ticket,symbol,order_ticket,type,magic,volume,open_price,
        #               open_time,sl,tp,close_price,close_time,comment,profit,swap,commission
        return {
            "ticket": int(float(y[0])),
            "symbol": y[1],
            "type": "buy" if y[3].lower() in ("buy", "0") else "sell",
            "volume": float(y[5]),
            "open_price": float(y[6]),
            "open_time": int(float(y[7])),
            "close_price": float(y[10]),
            "close_time": int(float(y[11])),
            "profit": float(y[13]),
            "swap": float(y[14]),
            "commission": float(y[15]),
        }

    @staticmethod
    def _parse_open(rec: str) -> dict:
        y = rec.split("$")
        # V4.01 open: ticket,symbol,order_ticket,type,magic,volume,open_price,
        #             open_time,sl,tp,comment,profit,swap,commission
        return {
            "ticket": int(float(y[0])),
            "symbol": y[1],
            "type": "buy" if y[3].lower() in ("buy", "0") else "sell",
            "volume": float(y[5]),
            "open_price": float(y[6]),
            "open_time": int(float(y[7])),
            "close_price": None,
            "close_time": None,
            "profit": float(y[11]),
            "swap": float(y[12]),
            "commission": float(y[13]),
        }

    # ---- data -----------------------------------------------------------
    def closed_positions(self, since_ts: int, until_ts: int) -> list[dict]:
        d1 = time.strftime(DATE_FMT, time.gmtime(since_ts))
        d2 = time.strftime(DATE_FMT, time.gmtime(until_ts))
        recs = self._records(self._send(f"F062^{d1}^{d2}^"), "F062")
        return [self._parse_closed(r) for r in recs if r.strip()]

    def open_positions(self) -> list[dict]:
        recs = self._records(self._send("F061^1^"), "F061")
        return [self._parse_open(r) for r in recs if r.strip()]

    def balance_operations(self, since_ts: int, until_ts: int) -> list[dict]:
        # Protokol PyTrader tidak mengekspor operasi balance/deposit.
        return []
