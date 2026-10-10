"""Penyimpanan multi-akun trading.

Aturan keamanan:
- Password TIDAK PERNAH disimpan polos -> dienkripsi Fernet (kunci dari env).
- Password TIDAK PERNAH dikembalikan oleh metode apa pun di modul ini.
- File data berada di backend/data/accounts.json (di-gitignore).
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import uuid
from typing import Optional

import config


class StoreError(Exception):
    pass


class AccountStore:
    def __init__(self, path=None, secret_key: str = ""):
        self._path = str(path or config.ACCOUNTS_FILE)
        self._lock = threading.RLock()
        self._fernet = self._make_fernet(secret_key or config.SECRET_KEY)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    @staticmethod
    def _make_fernet(key: str):
        from cryptography.fernet import Fernet
        if key:
            try:
                return Fernet(key.encode()), True
            except Exception:
                raise StoreError(
                    "TRADING_SECRET_KEY tidak valid. Buat dengan: "
                    "python -c \"from cryptography.fernet import Fernet;"
                    "print(Fernet.generate_key().decode())\"")
        # Tanpa kunci env -> kunci acak per proses (password tak bisa
        # dipulihkan setelah restart; hanya cocok untuk mode coba-coba).
        return Fernet(Fernet.generate_key()), False

    @property
    def persistent_encryption(self) -> bool:
        return self._fernet[1]

    # ---- I/O -----------------------------------------------------------
    def _read(self) -> dict:
        if not os.path.exists(self._path):
            return {"accounts": [], "active": None}
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self._path)
        try:  # batasi izin file (berisi password terenkripsi)
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    # ---- operasi ---------------------------------------------------------
    def list(self) -> list[dict]:
        with self._lock:
            return [self._public(a) for a in self._read()["accounts"]]

    @staticmethod
    def _public(a: dict) -> dict:
        return {k: v for k, v in a.items()
                if k not in ("password_enc", "password")}

    def get(self, account_id: str) -> Optional[dict]:
        with self._lock:
            for a in self._read()["accounts"]:
                if a["id"] == account_id:
                    return a
        return None

    def add(self, platform: str, login: str = "", password: str = "",
            server: str = "", label: str = "", extra: Optional[dict] = None,
            max_accounts: int = 20) -> dict:
        with self._lock:
            data = self._read()
            if len(data["accounts"]) >= max_accounts:
                raise StoreError(
                    f"Jumlah akun maksimal {max_accounts}. Hapus salah satu dulu.")
            acc = {
                "id": uuid.uuid4().hex[:12],
                "platform": platform,
                "login": str(login),
                "server": str(server),
                "label": str(label or (f"{platform.upper()} {login}" if login
                                       else "Demonstrasi")),
                "extra": dict(extra or {}),
                "created_at": int(time.time()),
            }
            if password:
                enc = self._fernet[0].encrypt(str(password).encode())
                acc["password_enc"] = enc.decode()
            data["accounts"].append(acc)
            if data.get("active") is None:
                data["active"] = acc["id"]
            self._write(data)
            return self._public(acc)

    def delete(self, account_id: str) -> None:
        with self._lock:
            data = self._read()
            before = len(data["accounts"])
            data["accounts"] = [a for a in data["accounts"]
                                if a["id"] != account_id]
            if len(data["accounts"]) == before:
                raise StoreError("Akun tidak ditemukan.")
            if data.get("active") == account_id:
                data["active"] = (data["accounts"][0]["id"]
                                  if data["accounts"] else None)
            self._write(data)

    def set_active(self, account_id: str) -> None:
        with self._lock:
            data = self._read()
            if not any(a["id"] == account_id for a in data["accounts"]):
                raise StoreError("Akun tidak ditemukan.")
            data["active"] = account_id
            self._write(data)

    def active_id(self) -> Optional[str]:
        with self._lock:
            return self._read().get("active")

    def decrypt_password(self, account_id: str) -> str:
        """Dipakai backend SAJA saat membuat koneksi. Tidak pernah keluar API."""
        acc = self.get(account_id)
        if not acc:
            raise StoreError("Akun tidak ditemukan.")
        enc = acc.get("password_enc")
        if not enc:
            return ""
        return self._fernet[0].decrypt(enc.encode()).decode()
