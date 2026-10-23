# CHECKPOINT.md — Trading Assistant XAUUSD

> Update file ini setiap kali selesai satu task. Baca sebelum mulai task baru.

---

## Status Terakhir

**Tanggal:** 2026-10-23  
**Status overall:** 🟡 PARTIAL — bot jalan tapi ada bug kritis

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
**Status:** 🔴 OPEN  
**Gejala:** Bot return `STANDBY` dengan alasan `GEO_UNKNOWN` padahal geopolitics NONAKTIF di v1.0  
**Lokasi:** `src/assistant/runner.py` — geopolitics filter masuk ke chain evaluasi  
**Fix:** Hapus/bypass geopolitics dari evaluation chain di runner.py  

### BUG-002 — Simbol salah
**Status:** 🔴 OPEN  
**Gejala:** Run dengan `--symbol XAUUSD` tapi connect ke `XAUUSDm`  
**Lokasi:** `config/broker.toml` atau `src/broker/config.py`  
**Fix:** Pastikan symbol mapping benar sesuai broker aktif  

---

## Yang Belum Dikerjakan

- [ ] Fix BUG-001 — hapus geopolitics dari runner evaluation chain
- [ ] Fix BUG-002 — symbol mapping
- [ ] Validasi output laporan Telegram
- [ ] Forward test demo — minimal 2 minggu
- [ ] `CLAUDE.md`, `CHECKPOINT.md`, `DECISIONS.md` di repo ← sedang dibuat

---

## Catatan

- Bot sudah bisa connect ke MT5 dan disconnect dengan benar
- Output console dan Telegram sudah jalan
- Evaluasi status belum akurat karena BUG-001
