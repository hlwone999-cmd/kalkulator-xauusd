# Fitur Akun Trading MT4/MT5 + Dashboard Statistik

Fitur tambahan untuk Kalkulator Lot XAUUSD — **terpisah total dari kalkulator lama**.
Kalkulator (index.html, style.css, script.js) tidak diubah algoritmanya; satu-satunya
sentuhan adalah satu tautan navigasi di header index.html.

## Arsitektur

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│ Frontend (statis)       │  HTTP  │ Backend Python (Flask)       │
│ trading.html/css/js     │ ─────► │ backend/app.py  /api/trading │
│ Halaman koneksi +       │        │ ├── connectors/mt5_api.py    │
│ dashboard statistik     │        │ ├── connectors/mt4_pytrader  │
└─────────────────────────┘        │ ├── connectors/demo.py       │
        index.html kalkulator      │ ├── services/store.py (enkripsi)
        TIDAK ikut berubah         │ └── services/stats.py        │
                                   └──────────┬───────────────────┘
                                              │
                        ┌─────────────────────┴────────────────────┐
                        ▼                                          ▼
              Paket resmi MetaTrader5                   EA PyTrader (bridge TCP)
              (Windows + terminal MT5)                  di terminal MT4/MT5
                                                        (Windows / Wine / VPS)
```

## Instalasi

```bash
# 1. Install dependensi backend
pip install -r backend/requirements.txt

# 2. (Disarankan) Siapkan kunci enkripsi + token API
cp backend/.env.example backend/.env   # lalu isi nilainya, atau set sebagai env:
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
export TRADING_SECRET_KEY="<hasil generate>"
export TRADING_API_TOKEN="<token rahasia pilihanmu>"

# 3. Jalankan backend (menyajikan kalkulator lama + halaman trading sekaligus)
python backend/app.py

# 4. Buka di browser
#    Kalkulator : http://127.0.0.1:5000/            (persis seperti sebelumnya)
#    Trading    : http://127.0.0.1:5000/trading.html
```

Tanpa backend, halaman `trading.html` tetap terbuka (mis. dari GitHub Pages) dan
menampilkan banner "Backend tidak aktif" — kalkulator tetap berfungsi normal.

## Konektor

| Platform | Cara kerja | Persyaratan | Status pengujian di repo ini |
|---|---|---|---|
| **MT5** | Paket resmi `MetaTrader5` (`initialize(login,password,server)`, `history_deals_get`, `positions_get`) | **Windows** + terminal MT5 terpasang & pernah dibuka; `pip install MetaTrader5` | Unit test dengan modul tiruan. Koneksi nyata **belum bisa diuji** di lingkungan Linux ini |
| **MT4** | Protokol **PyTrader**: EA berjalan di terminal MT4 dan membuka server TCP (default port 2345); backend mengirim perintah `F001`/`F002`/`F061`/`F062` dengan pemisah `^` dan terminator `!` | Terminal MT4 (Windows/Wine/VPS) + EA PyTrader terpasang & aktif; IP/port bridge diisi di form | Unit test dengan socket tiruan sesuai format protokol. Koneksi nyata **belum bisa diuji** |
| **Demo** | Data contoh deterministik per seed, **diberi label DEMO di UI** | Tidak ada | Teruji penuh (dipakai untuk dashboard & pengujian) |

Field mapping protokol PyTrader mengikuti `Pytrader_API_V4_01.py` (format respons
`Fxxx^...^` dengan record dipisah `$`). Bila versi EA kamu berbeda dan field tidak
cocok, sesuaikan `_parse_static/_parse_open/_parse_closed` di
`backend/connectors/mt4_pytrader.py`.

## Deployment konektor (jujur soal kebutuhan lingkungan)

- Konektor MT5/MT4 **membutuhkan terminal MetaTrader yang berjalan**. Keduanya
  TIDAK bisa berjalan di hosting Linux biasa (mis. layanan cloud tanpa Windows).
- Pola deployment yang benar:
  1. Backend Flask berjalan di server (Linux boleh).
  2. Terminal MT4/MT5 + EA berjalan di **VPS Windows**, atau di komputer rumah
     yang sama dengan backend.
  3. Untuk MT4: isi "Alamat bridge MT4" dengan IP komputer VPS/komputer tersebut
     dan buka port 2345 di firewall (batasi ke IP backend, bukan publik penuh).
  4. Untuk MT5 di Windows: backend + `pip install MetaTrader5` + set
     `TRADING_MT5_PATH` bila terminal tidak di lokasi standar.
- Integrasi ini **read-only**: tidak ada endpoint membuka/menutup order.

## Keamanan

- Password akun **tidak pernah** dikirim balik ke frontend, tidak di log, tidak di
  URL; tersimpan terenkripsi Fernet (`backend/data/accounts.json`, di-gitignore,
  permission 0600).
- Tanpa `TRADING_SECRET_KEY`, kunci enkripsi acak per proses (password tersimpan
  tak terbaca setelah restart) — backend memberi peringatan di console.
- Set `TRADING_API_TOKEN` agar semua endpoint API butuh `Authorization: Bearer`.
- Backend tidak melayani file `backend/*` via web (404), termasuk data akun.
- Bila backend dipaparkan ke internet: gunakan HTTPS reverse proxy + token API.
  Ini aplikasi lokal/kantor, bukan sistem multi-pengguna.

## Metrik dashboard & definisi

- Trade = posisi tertutup (deal OUT). Deposit/withdrawal bukan trade.
- Win rate = menang / (menang + kalah); trade impas tidak masuk penyebut.
- Profit bersih per trade = profit + swap + komisi.
- Profit factor = gross profit / gross loss; bila tidak ada loss → "∞".
- Max drawdown = pada kurva balance (deposit + akumulasi hasil trade tertutup),
  bukan tick-per-tick — drawdown intratrade tidak terdeteksi.
- Waktu memakai waktu server broker (asumsi UTC).
- MT4 (protokol PyTrader) tidak mengekspor deposit/withdrawal → kolom deposit
  ditandai "tidak tersedia". MT5 mengekspornya dari deal bertipe BALANCE.

## Pengujian

```bash
cd backend
python -m pytest tests -q
```

38 pengujian: statistik (dataset diketahui), API (validasi, periode, multi-akun,
backend mati), keamanan (password tidak bocor di response/file, tidak ada endpoint
order, path backend terlarang), konektor (demo deterministik, MT5 fake, MT4
protokol fake), dan proteksi route statis.

**Regresi kalkulator**: baseline 20 metrik output kalkulator (lot otomatis, tabel
150 baris, matriks, pick row) diambil sebelum dan sesudah pengembangan — hasilnya
IDENTIK. `script.js` dan `style.css` tidak berubah (0 baris diff).

## Keterbatasan yang belum bisa diuji (transparan)

1. Koneksi MT5 nyata — butuh Windows + terminal; lingkungan pengembangan ini Linux.
2. Koneksi MT4 nyata ke EA PyTrader — butuh terminal MT4 + EA berjalan.
3. Field bridge MT4 bisa berbeda antar versi EA (V3.02c vs V4.01).
4. Statistik belum mencakup: partial-close yang digabung per position_id
   (deal OUT diperlakukan sebagai trade tersendiri), akun netting dengan
   deposito berkeliaran, dan koreksi timezone broker.
5. Autentikasi API sederhana (bearer token) — bukan sistem user multi-tenant.
