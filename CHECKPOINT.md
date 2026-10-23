# CHECKPOINT.md — Trading Assistant XAUUSD

> Update file ini setiap kali selesai satu task. Baca sebelum mulai task baru.

---

## Status Terakhir

**Tanggal:** 2026-10-23  
**Status overall:** 🟡 PARTIAL — semua bug CRITICAL dan WARNING dari audit serta BUG-002 sudah diperbaiki; temuan INFO masih open

---

## Yang Sudah Selesai

### Infrastruktur
- [x] Struktur folder project
- [x] `src/broker/client.py` — koneksi MT5
- [x] `src/broker/config.py` — config loader
- [x] `src/broker/credentials.py` — credentials handler
- [x] `src/broker/errors.py` — custom exceptions
- [x] `config/broker.toml` — konfigurasi broker
- [x] `requirements.txt`, `requirements-dev.txt`, `requirements-mt5.txt`
- [x] `.env.example`

### Models
- [x] `src/models/enums.py`
- [x] `src/models/market.py`
- [x] `src/models/news.py`
- [x] `src/models/trading.py`
- [x] `src/models/advice.py`
- [x] `src/models/account.py`
- [x] `src/models/_validation.py`

### Analysis
- [x] `src/analysis/h1_sr.py`
- [x] `src/analysis/m15_bias.py`
- [x] `src/analysis/m30_structure.py`
- [x] `src/analysis/m5_rejection.py`

### Filters
- [x] `src/filters/news.py`
- [x] `src/filters/geopolitics.py` ⚠️ NONAKTIF — tidak masuk v1.0
- [x] `src/filters/macro.py` ⚠️ NONAKTIF — tidak masuk v1.0

### Assistant
- [x] `src/assistant/planner.py`
- [x] `src/assistant/runner.py`

### Scripts
- [x] `scripts/run_assistant.py`
- [x] `scripts/broker_check.py`

### Data
- [x] `data/calendar/usd_high_impact.csv`
- [x] `data/calendar/build_calendar.py`

### Tests
- [x] `tests/test_broker.py`
- [x] `tests/test_models.py`
- [x] `tests/test_news_calendar.py`

---

## Bug Kritis — Harus Diselesaikan

### BUG-001 — Geopolitics DAN Macro aktif di evaluation chain
**Status:** ✅ FIXED — `7f7bab3` (2026-10-23)  
**Gejala:** Bot return `STANDBY` dengan alasan `GEO_UNKNOWN` padahal geopolitics NONAKTIF di v1.0. Macro juga ikut: `check_macro_filter()` selalu `MACRO_UNKNOWN`, dan `check_geopolitical_risk(None)` selalu `GEO_UNKNOWN` → **BOT tidak akan pernah bisa VALID**.  
**Lokasi:** `src/assistant/runner.py:36-37, 82-91, 121-123, 129-131`; `src/assistant/planner.py:288-289, 320-346` (gate geo + macro antara news dan bias)  
**Fix:** Hapus geopolitics & macro dari runner dan dari gate planner (DEC-002)  

### BUG-002 — Simbol salah
**Status:** ✅ FIXED — commit remote `e0197f7` + `f4382d8`, digabung di merge 2026-10-23  
**Gejala:** Run dengan `--symbol XAUUSD` tapi connect ke `XAUUSDm`  
**Lokasi:** `config/broker.toml` atau `src/broker/config.py`  
**Fix:** `load_broker_config(path, symbol=...)` menimpa symbol TOML dengan symbol dari `--symbol` sebelum validasi; runner memakainya dan mencatat symbol yang dipakai di log.  
**Catatan audit:** Kode sekarang (`runner.py:59-60`) menimpa `config.symbol` dengan argumen CLI, jadi `--symbol XAUUSD` seharusnya connect ke `XAUUSD`. Gejala perlu direproduksi ulang. `DEFAULT_SYMBOL = "XAUUSDm"` di-hardcode di `runner.py:42`, duplikat dari `broker.toml` → dua sumber kebenaran.

---

## BUG List — Hasil Audit Menyeluruh (2026-10-23)

> Audit saja, belum ada perbaikan. Acuan: CLAUDE.md + DECISIONS.md (file spesifikasi `BOT_SemiAuto_XAUUSD_Spesifikasi_Final_v1.0.md` tidak ada di repo).

### 🔴 CRITICAL

**BUG-003 — Gate SL salah: rentang 0.8×–2.0× Risk_ATR, bukan ≤ 1.5×**  
✅ **FIXED** — `f3ad8e0` (2026-10-23)  
`src/analysis/m5_rejection.py:35-36, 329-334` dan `src/assistant/planner.py:25-26, 439-454`. Spek (DEC-007): lolos hanya jika `Risk_Struct ≤ Risk_ATR × 1.5`. Kode meloloskan SL sampai 2.0× (terlalu longgar) dan menolak SL < 0.8× (batas bawah tidak ada di spek). Pesan alasan juga menyebut "0.8x-2.0x".

**BUG-004 — Kedaluwarsa Entry Zone (DEC-006) tidak diimplementasi**  
✅ **FIXED** — `1babd9e` (2026-10-23)  
`src/assistant/planner.py` (tidak ada logika), `src/assistant/runner.py:126-134`. Planner tidak menerima harga terkini sama sekali, jadi tidak bisa cek apakah harga > 1.0 × ATR M5 dari batas zona. Rencana basi tetap dikirim sebagai VALID.

**BUG-005 — Engulfing pakai batas tidak ketat**  
✅ **FIXED** — `d2c7dd9` (2026-10-23)  
`src/analysis/m5_rejection.py:173-175` pakai `body_low <= prev_low and body_high >= prev_high`. DEC-005 wajib `<` dan `>` ketat; body sama persis saat ini dihitung engulfing.

**BUG-006 — Urutan H1 S/R salah: swing dibatasi 3 SEBELUM digabung**  
✅ **FIXED** — `6242ab6` (2026-10-23)  
`src/analysis/h1_sr.py:23, 92-106`. `_confirmed_swings` berhenti setelah 3 swing high + 3 swing low terbaru, baru kemudian di-cluster dan dipilih. DEC-004: kumpulkan SEMUA swing dalam 60 candle → gabung ≤ 1.50 → pilih 3 terdekat. Swing lama yang lebih dekat ke harga hilang.

**BUG-007 — Level SL struktur bisa sama dengan level entry**  
✅ **FIXED** — `a128434` (2026-10-23)  
`src/analysis/m5_rejection.py:302-310` + `451-455, 480-492`. Entry Zone dipusatkan pada level H1 (`entry = entry_level`), lalu `_structural_stop_level` memilih level H1 `<= entry` → level yang sama terpilih → SL = entry − 0.40 USD. Saat ini tertutup oleh batas bawah 0.8× (BUG-003); begitu BUG-003 diperbaiki, bot akan VALID dengan SL 0.40 USD yang tidak bermakna secara struktur. Harus diperbaiki bersamaan dengan BUG-003.  
**Interpretasi fix (DEC-010):** level SL struktur harus berada di luar Entry Zone (BUY: `< zone.low`, SELL: `> zone.high`); level pusat zona tidak dipakai sebagai SL.

### 🟡 WARNING

**BUG-008 — M30 tidak punya status UNCLEAR; swing kurang → DATA_INVALID**  
✅ **FIXED** — `7191ccc` (2026-10-23)  
`src/analysis/m30_structure.py:27-33, 196-199`; `src/assistant/planner.py:284` (set status M30 tanpa UNCLEAR). Pasar tanpa 2 swing high + 2 swing low dilaporkan `DATA_INVALID` untuk seluruh siklus, padahal spek: UNCLEAR → STANDBY. Tabel konflik M30 vs M15 (DEC-008) sendiri sudah benar di `planner.py:348-368`.

**BUG-009 — Candle "tertutup" hanya berdasarkan posisi, tanpa validasi timestamp**  
✅ **FIXED** — `52164a0` (2026-10-23)  
`src/broker/client.py:206-207` membuang baris terakhir begitu saja. DEC-009 mewajibkan validasi timestamp. Tidak ada cek kesegaran data (weekend / feed macet / koneksi putus) di runner langkah 1 → analisis bisa jalan di atas data basi dan tetap menghasilkan VALID. Modul analysis tidak memvalidasi penutupan sendiri (bergantung penuh pada broker).

**BUG-010 — Kalender news habis 2026-12-23 → setelah itu selalu CLEAR**  
✅ **FIXED** — `65cc8fa` (2026-10-23)  
`src/filters/news.py:206-214`; `data/calendar/usd_high_impact.csv` (baris terakhir 2026-12-23). Jika `now` melewati cakupan kalender, hasilnya `CLEAR` dengan `next_event=None`. Seharusnya `NEWS_UNKNOWN` (semangat DEC-003). Bom waktu ±2 bulan lagi.

**BUG-011 — Harga terkini H1 = close candle H1 tertutup terakhir**  
✅ **FIXED** — `e03ed2b` (2026-10-23)  
`src/analysis/h1_sr.py:168`. Bisa basi hingga ~60 menit; pembagian support/resistance dan pemilihan zona terdekat memakai harga itu.

**BUG-012 — ATR M5 ikut menghitung candle rejection itu sendiri**  
✅ **FIXED** — `127fafa` (2026-10-23)  
`src/analysis/m5_rejection.py:138-142, 399-411`. Filter `range ≥ 0.8 × ATR(14)` bersifat self-referential (range candle ikut menaikkan ATR). Perlu keputusan: ATR dari 14 candle sebelum candle sinyal atau termasuk.  
**Keputusan (2026-10-23, DEC-011):** ATR dari 14 candle **sebelum** candle sinyal. M5 sekarang butuh minimal 16 candle; runner mengambil 20.

**BUG-013 — Broker client masih punya fungsi eksekusi order**  
✅ **FIXED** — `b0f2394` (2026-10-23)  
`src/broker/client.py:303-477` (`_order_send`, `close_position`, `modify_sltp`, `cancel_order`). Tidak dipanggil runner, tapi bertentangan dengan DEC-001 (BOT hanya analisis). Sebaiknya dihapus/diisolasi.

**BUG-014 — Tidak ada test untuk logika inti; pytest tidak terpasang**  
✅ **FIXED** — `d3acbaa` + `65cc8fa` (2026-10-23): test untuk semua modul analysis, planner, runner, dan news filter.  
Tidak ada test untuk `h1_sr`, `m30_structure`, `m15_bias`, `m5_rejection`, `planner`, `runner`, `filters/news.py` (test_news_calendar hanya cek integritas CSV). `python -m pytest` gagal: modul pytest tidak terpasang di Python 3.12 lokal → aturan "jangan commit jika test gagal" tidak bisa diverifikasi.

**BUG-015 — EMA50 M15 belum konvergen**  
✅ **FIXED** — `e1f46b5` (2026-10-23)  
`src/assistant/runner.py:48` (M15 = 60 candle), `src/analysis/m15_bias.py:24, 78`. Seed SMA 50 candle + hanya 10 iterasi → nilai EMA50 berbeda signifikan dari EMA di MT5. Kondisi BULLISH/BEARISH/NEUTRAL sendiri sudah benar.

### 🔵 INFO

- **INFO-01** `h1_sr.py:121-126` — clustering berantai (bandingkan dengan level terakhir cluster), zona bisa melebar > 1.50 USD. Spek tidak tegas.
- **INFO-02** `h1_sr.py:138-139` — swing high di bawah harga dan swing low di atas harga dibuang (tidak ada role-reversal). Spek tidak tegas.
- **INFO-03** `m5_rejection.py:171-179` — Engulfing tidak mensyaratkan candle sebelumnya berlawanan arah.
- **INFO-04** `m5_rejection.py:33` — `Risk_ATR = 1.2 × ATR`; tidak bisa diverifikasi karena file spesifikasi tidak ada di repo.
- **INFO-05** Docstring usang: `runner.py:3-13`, `planner.py:3-15`, `m5_rejection.py:4-7` masih menyebut geopolitics/macro dan aturan 0.8×–2.0×.
- **INFO-06** `planner.py:398` — kondisional mati (status selalu VALID di titik itu).
- **INFO-07** `src/models/enums.py` — tidak ada enum status VALID/STANDBY/DATA_INVALID (status pakai string literal), `Trend` tanpa TRANSITION/UNCLEAR, sisa enum full-auto (`KillSwitchLevel`, `OrderOutcome`).
- **INFO-08** `requirements.txt` dan file spesifikasi v1.0 tidak ada di repo walau disebut di CLAUDE.md.

### ✅ Sesuai spek (tidak ada temuan)
- News di-gate sebelum bias; `NEWS_UNKNOWN` → STANDBY (`planner.py:306-318`); `news.py` fail-closed untuk file/parse error.
- Kondisi M15 BULLISH/BEARISH/NEUTRAL (`m15_bias.py:116-124`).
- Filter ATR 0.8× berlaku untuk Pin Bar dan Engulfing (`m5_rejection.py:409-417`).
- Range = 0 ditangani (`m5_rejection.py:151-153`).
- Konfirmasi swing H1/M30/M5 memakai 2 candle kanan (dengan asumsi input tertutup — lihat BUG-009).
- TP1 = 1.5R, TP2 = 2.5R dengan R = Risk_Struct (`m5_rejection.py:37-38, 336-343`).
- Lokasi ± 0.5 × ATR M5; buffer SL 0.40 USD (dalam 0.30–0.50).

---

## Yang Belum Dikerjakan

- [x] Fix BUG-002 — symbol mapping
- [x] Fix BUG-001, BUG-003 s/d BUG-007 (TDD, satu commit per bug)
- [x] Fix WARNING BUG-008 s/d BUG-015 (TDD, satu commit per bug)
- [x] Catat keputusan BUG-007 → DEC-010 dan BUG-012 → DEC-011 di DECISIONS.md
- [ ] Validasi output laporan Telegram
- [ ] Forward test demo — minimal 2 minggu
- [ ] `CLAUDE.md`, `CHECKPOINT.md`, `DECISIONS.md` di repo ← sedang dibuat

---

## Catatan

- Bot sudah bisa connect ke MT5 dan disconnect dengan benar
- Output console dan Telegram sudah jalan
- BUG-001 fixed: bot sekarang bisa menghasilkan `VALID`
- pytest terpasang (`pip install -r requirements-dev.txt`); test untuk planner, runner, H1, M30, M15, M5, news filter — 178 passed
- Jumlah candle runner: H1 60, M30 50, M15 250, M5 20
- Data basi (candle terbaru tiap TF lebih tua dari 1 slot) → `DATA_INVALID`; artinya saat market tutup (weekend, jeda harian) bot memang keluar `DATA_INVALID`
- Kalender news harus diperbarui sebelum 2026-12-23, setelah itu filter news keluar `NEWS_UNKNOWN` → STANDBY
- Planner sekarang butuh `current_price` (runner pakai `broker.tick().bid`); hasil M5 sekarang punya field `atr`
- Roadmap arsitektur dicatat di DEC-012 (2026-10-23): v1.0 Python + MT5 deterministik (AKTIF) → v2.0 Anthropic API (Sonnet 5.5) sebagai reasoning layer → v3.0 TradingView webhook + Cloudflare Tunnel + Windows VPS. v2.0/v3.0 baru dikerjakan setelah v1.0 terbukti akurat; belum ada perubahan kode.
