# CLAUDE.md — Trading Assistant XAUUSD

> Baca file ini sebelum menyentuh kode apapun.

## Identitas Project

**Nama:** Trading Assistant Semi-Auto XAUUSD  
**Repo:** Azalea-Nawawi/Trading-Assistant  
**Branch aktif:** main  
**Versi spesifikasi:** v1.0 (final)  
**Mode:** Semi-otomatis — analisis dan rekomendasi saja. BOT tidak membuka atau menutup posisi.

---

## Struktur Folder

```
Trading-Assistant/
├── config/
│   └── broker.toml          # Konfigurasi broker (symbol, server, dll)
├── data/
│   └── calendar/
│       ├── usd_high_impact.csv   # Data kalender berita USD high-impact
│       ├── build_calendar.py     # Script builder kalender
│       └── README.md
├── scripts/
│   ├── broker_check.py      # Cek koneksi broker MT5
│   └── run_assistant.py     # Entry point utama
├── src/
│   ├── analysis/
│   │   ├── h1_sr.py         # H1 Support & Resistance
│   │   ├── m15_bias.py      # M15 EMA bias
│   │   ├── m30_structure.py # M30 trend structure
│   │   └── m5_rejection.py  # M5 Pin Bar & Engulfing
│   ├── assistant/
│   │   ├── planner.py       # Hitung Entry Zone, SL, TP
│   │   └── runner.py        # Orkestrasi evaluasi status
│   ├── broker/
│   │   ├── client.py        # Koneksi MT5
│   │   ├── config.py        # Config loader
│   │   ├── credentials.py   # Credentials handler
│   │   └── errors.py        # Custom exceptions
│   ├── filters/
│   │   ├── news.py          # Filter berita ekonomi (AKTIF v1.0)
│   │   ├── geopolitics.py   # NONAKTIF — tidak masuk v1.0
│   │   └── macro.py         # NONAKTIF — tidak masuk v1.0
│   └── models/
│       ├── account.py
│       ├── advice.py
│       ├── enums.py         # Status enum: VALID, STANDBY, DATA_INVALID, dll
│       ├── market.py
│       ├── news.py
│       ├── trading.py
│       └── _validation.py
├── tests/
│   ├── test_broker.py
│   ├── test_models.py
│   └── test_news_calendar.py
├── .env.example
├── .env                     # Credentials (tidak di-commit)
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── requirements-mt5.txt
├── CLAUDE.md                # File ini
├── CHECKPOINT.md            # Progress tracking
└── DECISIONS.md             # Keputusan teknis
```

---

## Aturan Wajib

### Yang BOLEH dilakukan
- Modifikasi file dalam `src/`, `scripts/`, `tests/`, `config/`, `data/`
- Tambah file baru sesuai struktur folder yang ada
- Commit setelah setiap task selesai dan test pass

### Yang TIDAK BOLEH dilakukan
- Mengaktifkan `geopolitics.py` atau `macro.py` di evaluation chain — keduanya NONAKTIF di v1.0
- Menambahkan filter atau indikator baru yang tidak ada di spesifikasi v1.0
- Membuka atau menutup posisi MT5 — BOT ini hanya analisis
- Commit jika ada test yang gagal
- Menggunakan candle yang belum tertutup dalam perhitungan apapun

---

## Spesifikasi Teknikal Inti

### Status keluaran BOT
- `VALID` — semua syarat terpenuhi
- `STANDBY` — satu atau lebih syarat tidak terpenuhi (wajib ada alasan eksplisit)
- `DATA_INVALID` — data MT5 tidak valid atau tidak cukup

### Urutan evaluasi (runner.py)
1. Validasi data MT5 → gagal: `DATA_INVALID`
2. Filter news → blokir: `STANDBY`
3. Bias multi-timeframe sejalan? → tidak: `STANDBY`
4. Rejection valid + lokasi valid? → tidak: `STANDBY`
5. SL lolos filter ATR? → tidak: `STANDBY`
6. Semua lolos → `VALID`

### Filter yang aktif di v1.0
- `news.py` — AKTIF. `NEWS_UNKNOWN` tidak boleh diperlakukan sebagai `NEWS_CLEAR`
- `geopolitics.py` — NONAKTIF. Jangan dimasukkan ke evaluation chain
- `macro.py` — NONAKTIF. Jangan dimasukkan ke evaluation chain

### Aturan candle
- Semua perhitungan hanya menggunakan candle yang sudah tertutup
- Candle terakhir dari MT5 tidak otomatis dianggap tertutup

### H1 Support & Resistance
- Swing: high/low lebih tinggi/rendah dari 2 candle kiri dan 2 candle kanan
- Konfirmasi: 2 candle kanan sudah tertutup
- Lookback: 60 candle H1
- Pengelompokan: gabung level ≤ 1.50 USD → rata-rata → pilih 3 zona terdekat

### M30 Struktur
- Lookback: 40–50 candle M30
- UPTREND: HH + HL | DOWNTREND: LH + LL | TRANSITION/SIDEWAYS/UNCLEAR: lainnya

### M15 Bias
- BULLISH: harga > EMA21 > EMA50
- BEARISH: harga < EMA21 < EMA50
- NEUTRAL: selain itu

### M5 Setup
- Pin Bar: wick ≥ 60% range, close di setengah yang benar
- Engulfing: body menelan penuh (batas ketat — sama persis bukan engulfing)
- Filter ukuran: High−Low ≥ 0.8 × ATR(14)
- Lokasi: dekat S/R H1 atau Swing M30 (± 0.5 × ATR M5)

### Stop Loss
- SL Struktur = Swing M5/S/R H1 + buffer 0.30–0.50 USD
- Lolos jika: Risk_Struct ≤ Risk_ATR × 1.5
- Tidak lolos → STANDBY

### Take Profit
- R = Risk_Struct
- TP1 = Entry ± 1.5R
- TP2 = Entry ± 2.5R

---

## Stack Teknikal

- **Python 3.12**
- **MetaTrader5** — library koneksi MT5
- **Broker aktif:** sesuai `config/broker.toml`
- **Output:** console + Telegram

---

## Konvensi Commit

```
feat(scope): deskripsi singkat
fix(scope): deskripsi singkat
test(scope): deskripsi singkat
docs(scope): deskripsi singkat
```

Scope: `broker`, `analysis`, `filters`, `assistant`, `models`, `tests`

---

## Referensi

- Spesifikasi lengkap: `BOT_SemiAuto_XAUUSD_Spesifikasi_Final_v1.0.md`
- Progress: `CHECKPOINT.md`
- Keputusan teknis: `DECISIONS.md`
