# CHECKPOINT.md — Trading Assistant XAUUSD

> Update file ini setiap kali selesai satu task. Baca sebelum mulai task baru.

---

## Status Terakhir

**Tanggal:** 2026-10-23  
**Status overall:** 🟢 BUG-001 dan BUG-002 FIXED — evaluation chain v1.0 sudah aktif sesuai keputusan

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

### BUG-001 — Geopolitics filter aktif di evaluation chain
**Status:** ✅ FIXED  
**Gejala:** Bot return `STANDBY` dengan alasan `GEO_UNKNOWN` padahal geopolitics NONAKTIF di v1.0  
**Lokasi:** `src/assistant/runner.py` dan `src/assistant/planner.py`  
**Fix:** Geopolitics dan Macro tidak dipanggil serta hanya disimpan sebagai snapshot `INACTIVE`; keduanya tidak menjadi gate status.  

### BUG-002 — Simbol salah
**Status:** ✅ FIXED  
**Gejala:** Run dengan `--symbol XAUUSD` tapi connect ke `XAUUSDm`  
**Lokasi:** `src/assistant/runner.py` dan `src/broker/config.py`  
**Fix:** Symbol CLI diteruskan sebagai override tervalidasi ke BrokerConfig; koneksi menggunakan symbol yang diminta.  

---

## Yang Belum Dikerjakan

- [ ] Validasi output laporan Telegram
- [ ] Forward test demo — minimal 2 minggu
- [x] `CLAUDE.md`, `CHECKPOINT.md`, `DECISIONS.md` di repo

---

## Catatan

- Bot sudah bisa connect ke MT5 dan disconnect dengan benar
- Output console dan Telegram sudah jalan
- Runner tidak lagi memanggil geopolitics/macro; output menggunakan status `INACTIVE`
- Symbol dari `--symbol` diteruskan konsisten sampai `MT5Broker`
