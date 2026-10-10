"""Konfigurasi backend Trading Account — dibaca dari environment variables.

Tidak ada rahasia yang di-hardcode. Semua nilai sensitif via env.
"""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"


def _bool(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


# Kunci enkripsi password akun (Fernet). WAJIB diset di produksi.
# Contoh generate: python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
SECRET_KEY = os.environ.get("TRADING_SECRET_KEY", "").strip()

# Token API (opsional). Jika diset, semua endpoint /api/trading/* butuh
# header: Authorization: Bearer <token>
API_TOKEN = os.environ.get("TRADING_API_TOKEN", "").strip()

# Izinkan CORS (untuk frontend yang di-host terpisah, mis. GitHub Pages
# sambil backend jalan lokal). Default mati karena frontend disajikan
# dari Flask yang sama.
CORS_ENABLED = _bool("TRADING_CORS", "0")

# Path terminal MT5 (opsional, Windows saja), contoh:
# C:\Program Files\MetaTrader 5\terminal64.exe
MT5_TERMINAL_PATH = os.environ.get("TRADING_MT5_PATH", "").strip()

# Batas jumlah akun tersimpan (mencegah penyalahgunaan)
MAX_ACCOUNTS = int(os.environ.get("TRADING_MAX_ACCOUNTS", "20"))
