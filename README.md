# Kalkulator Lot XAUUSD (IDR)

Kalkulator lot untuk trading XAUUSD dengan akun berdenominasi Rupiah. Cukup isi **maksimal SL (pips)**, balance, dan risk %, lalu lot dihitung otomatis. Dilengkapi tabel semua lot, matriks risk %, dan simulasi Monte Carlo.

## Cara pakai

1. Ekstrak ZIP.
2. Buka `index.html` di browser (klik dua kali). Tidak perlu install apa pun.

Butuh internet hanya untuk font Google dan kurs USD/IDR live. Kalau offline, kalkulator tetap jalan dengan kurs yang kamu isi manual.

## Isi file

| File | Fungsi |
|---|---|
| `index.html` | Struktur halaman |
| `style.css` | Tampilan (otomatis mengikuti mode gelap/terang perangkat) |
| `script.js` | Semua logika: kalkulasi lot, tabel, kurs live, export CSV, Monte Carlo |

## Algoritma

```
Risk (Rp)    = Balance × Risk %
Risk (USD)   = Risk (Rp) ÷ Kurs USD/IDR
Lot          = Risk (USD) ÷ (Maksimal SL pips × 10)     → dibulatkan ke BAWAH per 0.01
SL pips      = Risk (USD) ÷ (Lot × 10)                  → untuk tabel semua lot
TP pips      = SL pips × rasio R:R
Target (Rp)  = Risk (Rp) × rasio R:R
```

Asumsi XAUUSD: 1 lot = 100 oz, 1 pip = $0,10 per oz, sehingga **0,01 lot × 10 pips = $1**. Cek contract size di broker kamu; beberapa broker atau akun cent berbeda. Angka `10` pada rumus di atas adalah nilai $ per pip untuk 1 lot (100 oz × $0,10). Kalau contract size brokermu berbeda, ubah angka itu di `script.js`.

## Fitur

- **Lot otomatis** dari maksimal SL, lengkap dengan risiko aktual, TP pips, target profit, dan nilai per pip.
- **Tabel lot 0.01–1.50** (kelipatan 0.01) berisi SL pips, TP pips, risk, dan target.
- **Matriks SL pips × risk %** (1% sampai 100%) untuk semua lot.
- **Kurs live** dari API publik (open.er-api.com, cadangan frankfurter.app), tanpa API key. Tersedia juga tombol kurs tetap 10.000 untuk broker lokal.
- **Monte Carlo**: win rate, jumlah trade, spread/komisi, batas drawdown, compounding. Menampilkan peluang profit, ekspektasi per trade (R), win rate impas, drawdown, loss beruntun, dan grafik.
- **Export CSV** tabel lot.
- Input tersimpan otomatis di browser (localStorage).
- Format angka fleksibel: `10.000.000`, `10,000,000`, `10jt`, `150rb`.

## Kustomisasi

- Daftar lot: konstanta `LOTS` di `script.js`.
- Persentase kolom matriks: konstanta `PCTS`.
- Sumber kurs: array `KURS_SOURCES`.
- Warna: variabel CSS di bagian atas `style.css`.

## Catatan

- Spread, komisi, dan slippage belum masuk hitungan lot (hanya di Monte Carlo lewat kolom biaya).
- Hasil Monte Carlo hanya sebaik win rate yang diisi. Gunakan data dari catatan trading nyata atau backtest.
- Alat bantu hitung, bukan saran keuangan. CFD berisiko tinggi.
