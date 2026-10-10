"""Konektor MT5 memakai paket resmi `MetaTrader5` (hanya Windows + terminal terpasang).

Referensi cara kerja: PyTrader-python-mt4-mt5-trading-api-connector (TheSnowGuru)
memakai EA bridge; untuk MT5 kita pakai API resmi yang lebih andal.
Paket di-import secara lazy agar backend tetap bisa jalan di Linux (untuk
demo/dashboard) dan memberi pesan yang jelas bila paket tidak tersedia.
"""
from __future__ import annotations

import importlib
import time
from typing import Any

from .base import Connector, ConnectorError, ConnectorUnavailable


def _load_mt5() -> Any:
    try:
        return importlib.import_module("MetaTrader5")
    except ImportError:
        raise ConnectorUnavailable(
            "Paket MetaTrader5 tidak tersedia di server ini. "
            "Konektor MT5 membutuhkan Windows dengan terminal MetaTrader 5 "
            "terpasang (lihat docs/MT4-MT5-FITUR.md bagian Deployment)."
        )


class MT5Connector(Connector):
    platform = "mt5"
    mode = "live"

    def __init__(self, login: int, password: str, server: str,
                 terminal_path: str = ""):
        if not (login and password and server):
            raise ConnectorError("Login, password, dan server MT5 wajib diisi.")
        self._login = int(login)
        self._password = str(password)
        self._server = str(server)
        self._path = terminal_path or None
        self._mt5: Any = None
        self._connected = False

    # ---- siklus hidup -------------------------------------------------
    def connect(self) -> dict:
        mt5 = _load_mt5()
        self._mt5 = mt5
        kwargs: dict[str, Any] = {"login": self._login,
                                  "password": self._password,
                                  "server": self._server}
        if self._path:
            kwargs["path"] = self._path
        if not mt5.initialize(**kwargs):
            err = mt5.last_error()
            raise ConnectorError(
                f"Gagal terhubung ke terminal MT5 ({err[0]}). "
                "Periksa login/password/server dan pastikan terminal MT5 "
                "terpasang serta sudah pernah dibuka minimal sekali."
            )
        info = mt5.account_info()
        if info is None:
            mt5.shutdown()
            raise ConnectorError(
                "Terminal terhubung tetapi info akun tidak terbaca. "
                "Pastikan akun sudah login di terminal MT5."
            )
        self._connected = True
        return {
            "login": str(info.login),
            "name": info.name,
            "broker": info.company,
            "server": info.server,
            "currency": info.currency,
            "balance": round(float(info.balance), 2),
            "equity": round(float(info.equity), 2),
            "leverage": int(info.leverage),
            "platform": self.platform,
        }

    def disconnect(self) -> None:
        if self._mt5 is not None:
            try:
                self._mt5.shutdown()
            finally:
                self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # ---- data ---------------------------------------------------------
    def _deals(self, since_ts: int, until_ts: int) -> list[Any]:
        mt5 = self._mt5
        deals = mt5.history_deals_get(since_ts, until_ts + 60)
        if deals is None:
            raise ConnectorError("Riwayat transaksi tidak bisa diambil dari terminal.")
        return list(deals)

    def closed_positions(self, since_ts: int, until_ts: int) -> list[dict]:
        out = []
        for d in self._deals(since_ts, until_ts):
            if d.entry != self._mt5.DEAL_ENTRY_OUT:
                continue
            if d.type not in (self._mt5.DEAL_TYPE_BUY, self._mt5.DEAL_TYPE_SELL):
                continue
            out.append({
                "ticket": d.ticket,
                "symbol": d.symbol,
                "type": "buy" if d.type == self._mt5.DEAL_TYPE_BUY else "sell",
                "volume": float(d.volume),
                "open_time": None,  # deal OUT tidak memuat open time; diisi lewat position_id bila perlu
                "close_time": int(d.time),
                "open_price": None,
                "close_price": float(d.price) if d.price else None,
                "profit": float(d.profit),
                "swap": float(d.swap),
                "commission": float(d.commission),
                "position_id": d.position_id,
            })
        return out

    def open_positions(self) -> list[dict]:
        mt5 = self._mt5
        poss = mt5.positions_get() or []
        return [{
            "ticket": p.ticket,
            "symbol": p.symbol,
            "type": "buy" if p.type == mt5.POSITION_TYPE_BUY else "sell",
            "volume": float(p.volume),
            "open_time": int(p.time),
            "close_time": None,
            "open_price": float(p.price_open),
            "close_price": None,
            "profit": float(p.profit),
            "swap": float(p.swap),
            "commission": 0.0,
        } for p in poss]

    def balance_operations(self, since_ts: int, until_ts: int) -> list[dict]:
        out = []
        for d in self._deals(since_ts, until_ts):
            if d.type != self._mt5.DEAL_TYPE_BALANCE:
                continue
            kind = "deposit" if d.profit >= 0 else "withdrawal"
            out.append({"time": int(d.time), "type": kind, "amount": float(d.profit)})
        return out

    def dynamic_info(self) -> dict:
        info = self._mt5.account_info()
        if info is None:
            raise ConnectorError("Koneksi MT5 terputus, silakan hubungkan ulang.")
        return {"balance": round(float(info.balance), 2),
                "equity": round(float(info.equity), 2)}
