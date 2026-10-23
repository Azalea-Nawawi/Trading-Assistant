# DECISIONS.md — Trading Assistant XAUUSD

> Setiap keputusan teknis dicatat di sini. Jangan ubah keputusan yang sudah ada tanpa diskusi dengan Tuan Muda.

---

## DEC-001 — Mode Operasi

**Tanggal:** 2026-10-23  
**Keputusan:** BOT beroperasi sebagai asisten analisis semi-otomatis. Tidak membuka, menutup, atau memodifikasi posisi di MT5.  
**Alasan:** Kendali penuh di tangan trader. Validasi strategi dulu sebelum otomasi.

---

## DEC-002 — Filter Aktif di v1.0

**Tanggal:** 2026-10-23  
**Keputusan:**
- `news.py` — AKTIF
- `geopolitics.py` — NONAKTIF, ditunda ke versi berikutnya
- `macro.py` — NONAKTIF, ditunda ke versi berikutnya

**Alasan:** Geopolitik dan makro memerlukan sumber data dan kriteria objektif yang belum ditetapkan. Memasukkan filter yang belum terdefinisi berisiko menghasilkan status menyesatkan.  
**Implikasi kode:** `runner.py` tidak boleh memanggil `geopolitics.py` atau `macro.py` dalam evaluation chain.

---

## DEC-003 — NEWS_UNKNOWN tidak sama dengan NEWS_CLEAR

**Tanggal:** 2026-10-23  
**Keputusan:** Jika kalender berita gagal diakses atau data tidak valid, status adalah `NEWS_UNKNOWN` dan BOT harus return `STANDBY` — bukan melanjutkan evaluasi.  
**Alasan:** Diam-diam menganggap kondisi tidak diketahui sebagai aman adalah risiko yang tidak dapat diterima.

---

## DEC-004 — Algoritma Pengelompokan Zona S/R H1

**Tanggal:** 2026-10-23  
**Keputusan:** Urutan proses wajib:
1. Kumpulkan semua swing terkonfirmasi dalam lookback 60 candle
2. Gabungkan level yang jaraknya ≤ 1.50 USD → harga zona = rata-rata
3. Pilih 3 zona Resistance + 3 zona Support terdekat dari harga saat ini

**Alasan:** Mencegah perbedaan hasil antara dua implementasi yang menerima data candle sama.

---

## DEC-005 — Definisi Engulfing (Batas Ketat)

**Tanggal:** 2026-10-23  
**Keputusan:** Body candle saat ini harus menelan body candle sebelumnya secara penuh dengan batas ketat:
- `Body_now_low < Body_prev_low` (strict less than)
- `Body_now_high > Body_prev_high` (strict greater than)
- Body yang sama persis **bukan** engulfing

**Alasan:** Menghindari ambiguitas interpretasi antara programmer yang berbeda.

---

## DEC-006 — Kedaluwarsa Entry Zone

**Tanggal:** 2026-10-23  
**Keputusan:** Jika harga saat laporan dikirim sudah bergerak lebih dari 1.0 × ATR M5 dari batas zona, rencana entry dinyatakan tidak relevan. BOT kirim `STANDBY` dengan alasan "harga telah meninggalkan Entry Zone."  
**Alasan:** Mencegah BOT mengirim rencana yang sudah basi.

---

## DEC-007 — Aturan Keputusan SL

**Tanggal:** 2026-10-23  
**Keputusan:** Struktur sebagai prioritas, ATR sebagai filter kelayakan:
- SL utama = level struktur + buffer 0.30–0.50 USD
- Lolos jika: `Risk_Struct ≤ Risk_ATR × 1.5`
- Jika tidak lolos → `STANDBY` (alasan: SL terlalu jauh)
- SL tidak boleh dipindahkan lebih dekat hanya untuk memenuhi batas ATR jika merusak logika struktur

**Alasan:** Menjaga konsistensi antara logika teknikal dan kelayakan risiko.

---

## DEC-008 — Konflik Bias M30 vs M15

**Tanggal:** 2026-10-23  
**Keputusan:** Tabel keputusan lengkap:

| M30 | M15 | Keputusan |
|---|---|---|
| UPTREND | BULLISH | Lanjut evaluasi |
| DOWNTREND | BEARISH | Lanjut evaluasi |
| UPTREND | NEUTRAL | STANDBY |
| DOWNTREND | NEUTRAL | STANDBY |
| UPTREND | BEARISH | STANDBY |
| DOWNTREND | BULLISH | STANDBY |
| SIDEWAYS/TRANSITION/UNCLEAR | Apapun | STANDBY |

**Alasan:** Bias harus sejalan di kedua timeframe sebelum setup M5 dievaluasi.

---

## DEC-009 — Candle yang Digunakan

**Tanggal:** 2026-10-23  
**Keputusan:** Semua perhitungan hanya menggunakan candle yang sudah tertutup. Candle terakhir dari MT5 tidak otomatis dianggap tertutup — implementasi harus memvalidasi timestamp.  
**Alasan:** Candle yang masih berjalan dapat berubah bentuk dan menghasilkan sinyal yang tidak valid.

---

## DEC-010 — Level SL Struktur Harus di Luar Entry Zone

**Tanggal:** 2026-10-23  
**Keputusan:** Level struktur untuk SL (Swing M5 atau S/R H1) hanya sah jika berada di luar Entry Zone, di sisi proteksi:
- BUY: level `< Entry_Zone.low` → dipilih level tertinggi yang memenuhi
- SELL: level `> Entry_Zone.high` → dipilih level terendah yang memenuhi
- Level yang menjadi pusat Entry Zone tidak pernah dipakai sebagai SL
- Tidak ada level yang memenuhi → `STANDBY` (tidak ada struktur yang jelas untuk SL)

SL = level terpilih ± buffer (DEC-007), lalu tetap harus lolos `Risk_Struct ≤ Risk_ATR × 1.5`.  
**Alasan:** Entry Zone dibangun di sekitar level H1/M30. Kalau level yang sama dipakai untuk SL, SL hanya sebesar buffer (0.40 USD) dari entry dan berada di dalam zona sendiri, jadi tidak bermakna secara struktur (BUG-007).  
**Implikasi kode:** `src/analysis/m5_rejection.py` — `_structural_stop_level` menerima `entry_zone`, bukan `entry`.

---

## DEC-011 — ATR M5 Tidak Menyertakan Candle Sinyal

**Tanggal:** 2026-10-23  
**Keputusan:** ATR(14) M5 dihitung dari 14 True Range candle tertutup **sebelum** candle rejection (candle sinyal). Range candle sinyal tidak ikut dihitung. ATR yang sama dipakai untuk:
- Filter ukuran rejection: `High − Low ≥ 0.8 × ATR`
- Toleransi lokasi: `± 0.5 × ATR`
- `Risk_ATR` (DEC-007)
- Kedaluwarsa Entry Zone: `1.0 × ATR` (DEC-006)

Akibatnya M5 butuh minimal 16 candle tertutup (15 untuk ATR + 1 candle sinyal); runner mengambil 20.  
**Alasan:** Kalau candle sinyal ikut dihitung, range-nya sendiri menaikkan ATR yang dipakai untuk menyaringnya, sehingga filter ukuran menjadi self-referential (BUG-012).  
**Implikasi kode:** `src/analysis/m5_rejection.py` (`_atr_sma(candles[:-1])`, `MIN_CANDLES = 16`), `src/assistant/runner.py` (`CANDLE_COUNTS[M5] = 20`).

---

## DEC-012 — Roadmap Arsitektur Bot

**Tanggal:** 2026-10-23  
**Keputusan:**
- **v1.0 (sekarang): Python + MT5 + logika deterministik — AKTIF**
- **v2.0:** tambah Anthropic API (Sonnet 5.5) sebagai reasoning layer — reasoning sinyal, confidence scoring, market narrative
- **v3.0:** TradingView webhook + Cloudflare Tunnel + Windows VPS — analisa candle via Pine Script, webhook ke Python bot

**Alasan:** Validasi strategi dulu via v1.0 sebelum menambah kompleksitas. API dan TradingView baru masuk setelah logika Python terbukti akurat.  
**Implikasi kode:** Tidak ada perubahan kode untuk sekarang.

---

## Template Keputusan Baru

```
## DEC-XXX — [Judul]

**Tanggal:** YYYY-MM-DD  
**Keputusan:** [Isi keputusan]  
**Alasan:** [Mengapa keputusan ini diambil]  
**Implikasi kode:** [File/fungsi yang terpengaruh, jika ada]
```
