"""Antarmuka dasar semua konektor akun trading (MT5 / MT4 / Demo).

Semua konektor mengembalikan struktur data ternormalisasi yang sama sehingga
dashboard tidak perlu tahu platform asalnya. Koneksi bersifat READ-ONLY:
tidak ada metode untuk membuka/menutup order.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class ConnectorError(Exception):
    """Kesalahan yang aman ditampilkan ke pengguna (tanpa bocor rahasia)."""


class ConnectorUnavailable(ConnectorError):
    """Konektor tidak bisa jalan di lingkungan ini
    (mis. paket MetaTrader5 hanya ada di Windows)."""


class Connector(ABC):
    platform: str = "base"
    mode: str = "live"  # "live" atau "demo"

    @abstractmethod
    def connect(self) -> dict:
        """Buat koneksi, kembalikan identitas akun ternormalisasi.

        Return dict: {login, name, broker, server, currency,
                      balance, equity, leverage, platform}
        Raise ConnectorError bila gagal dengan pesan ramah pengguna.
        """

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def closed_positions(self, since_ts: int, until_ts: int) -> list[dict]:
        """Riwayat posisi tertutup dalam rentang waktu (unix detik, UTC).

        Setiap item: {ticket, symbol, type:"buy"|"sell", volume, open_time,
        close_time, open_price, close_price, profit, swap, commission}
        """

    @abstractmethod
    def open_positions(self) -> list[dict]:
        """Posisi terbuka saat ini (struktur sama + tanpa close_time)."""

    @abstractmethod
    def balance_operations(self, since_ts: int, until_ts: int) -> list[dict]:
        """Operasi saldo (deposit/withdrawal) dalam rentang waktu.

        Setiap item: {time, type:"deposit"|"withdrawal"|"balance", amount}
        Boleh mengembalikan [] bila platform tidak menyediakannya.
        """

    def snapshot(self) -> dict:
        """Info akun dinamis (balance/equity/floating) saat ini."""
        positions = self.open_positions()
        floating = round(sum(p["profit"] + p.get("swap", 0) + p.get("commission", 0)
                             for p in positions), 2)
        info = self.dynamic_info()
        return {
            "balance": info["balance"],
            "equity": info["equity"],
            "floating": floating,
            "positions_open": len(positions),
        }

    def dynamic_info(self) -> dict:
        raise NotImplementedError
