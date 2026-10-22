# Kalender event high-impact USD (D-050)

Dipakai sama persis oleh backtest dan bot live untuk filter berita per hari
Strategy Spec #3 (D8). Satu baris per event: `date_et`, `time_et`
(America/New_York), `event`, `source`.

- **Cakupan:** 2023-10-18 sampai 2026-12-31. Hari di luar cakupan = tidak ada
  entry (fail-closed). Kalender 2027 wajib ditambahkan sebelum 2027-01-01.
- **Event (daftar tertutup D-050):** FOMC, NFP, CPI, PPI, RETAIL_SALES, PCE,
  GDP (semua rilis nasional), ISM_MANUFACTURING, ISM_SERVICES.
- **Isi:** 326 event di 287 hari.
- **Sumber:** situs resmi penerbit (Federal Reserve, BLS, BEA, Census Bureau,
  ISM) dan ALFRED (St. Louis Fed) untuk riwayat Retail Sales; URL per baris.
- **Catatan sumber:**
  - Penutupan pemerintahan AS Okt-Nov 2025: rilis yang tidak terbit (NFP,
    CPI, PPI, Retail Sales Oktober 2025; GDP advance Q3 2025 yang terjadwal
    2025-10-30) tidak dicatat; tanggal pengganti dicatat sesuai sumber.
  - BEA Okt-Des 2023 dari jadwal yang diterbitkan Des 2022 (planned).
  - ISM 2023-11 s.d. 2025-12 diturunkan dari aturan resmi ISM (hari kerja
    ke-1 Manufacturing, ke-3 Services, 10:00 ET) dengan hari libur federal
    AS, Jumat Agung, dan 2 Januari dikecualikan; aturan ini cocok 12/12
    dengan daftar resmi ISM 2026. ISM 2026 dari daftar resmi.
  - Revisi tahunan Retail Sales (ALFRED) tidak dicatat.
- **Regenerasi:** `python data/calendar/build_calendar.py` (dari folder
  `data/calendar`).
