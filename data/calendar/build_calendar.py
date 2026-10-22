import csv
from ism_rule import ism, official2026
FED="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BLS_E="https://www.bls.gov/bls/news-release/empsit.htm"; BLS_ES="https://www.bls.gov/schedule/news_release/empsit.htm"
BLS_C="https://www.bls.gov/bls/news-release/cpi.htm"; BLS_CS="https://www.bls.gov/schedule/news_release/cpi.htm"
BLS_P="https://www.bls.gov/bls/news-release/ppi.htm"; BLS_PS="https://www.bls.gov/schedule/news_release/ppi.htm"
ALF="https://alfred.stlouisfed.org/release/downloaddates?rid=9 (annual revisions excluded)"; CEN="https://www.census.gov/retail/release_schedule.html"
BEA23="https://apps.bea.gov/scb/issues/2022/12-december/1222-news-releases-2023.htm (planned schedule)"
BEA24="https://www.bea.gov/system/files/2024-06/2024-News-Release-Schedule.pdf"
BEA25="https://www.bea.gov/news/schedule/full-2025"; BEA26="https://www.bea.gov/news/schedule/full"
ISMO="https://ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/"
ISMR="ISM rule: Manufacturing = 1st business day, Services = 3rd business day, 10:00 ET (https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/); business days exclude weekends, US federal holidays, Good Friday, Jan 2; rule matches official 2026 list 12/12"
rows=[]
def add(ds,time,ev,src):
    for d in ds.split(): rows.append((d,time,ev,src))
add("2023-11-01 2023-12-13 2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28 2026-12-09","14:00","FOMC",FED)
add("2023-11-03 2023-12-08 2024-01-05 2024-02-02 2024-03-08 2024-04-05 2024-05-03 2024-06-07 2024-07-05 2024-08-02 2024-09-06 2024-10-04 2024-11-01 2024-12-06 2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06 2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16 2026-01-09 2026-02-11 2026-03-06 2026-04-03 2026-05-08 2026-06-05 2026-07-02 2026-08-07 2026-09-04 2026-10-02","08:30","NFP",BLS_E)
add("2026-11-06 2026-12-04","08:30","NFP",BLS_ES)
add("2023-11-14 2023-12-12 2024-01-11 2024-02-13 2024-03-12 2024-04-10 2024-05-15 2024-06-12 2024-07-11 2024-08-14 2024-09-11 2024-10-10 2024-11-13 2024-12-11 2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18 2026-01-13 2026-02-13 2026-03-11 2026-04-10 2026-05-12 2026-06-10 2026-07-14 2026-08-12 2026-09-11 2026-10-14","08:30","CPI",BLS_C)
add("2026-11-10 2026-12-10","08:30","CPI",BLS_CS)
add("2023-11-15 2023-12-13 2024-01-12 2024-02-16 2024-03-14 2024-04-11 2024-05-14 2024-06-13 2024-07-12 2024-08-13 2024-09-12 2024-10-11 2024-11-14 2024-12-12 2025-01-14 2025-02-13 2025-03-13 2025-04-11 2025-05-15 2025-06-12 2025-07-16 2025-08-14 2025-09-10 2025-11-25 2026-01-14 2026-01-30 2026-02-27 2026-03-18 2026-04-14 2026-05-13 2026-06-11 2026-07-15 2026-08-13 2026-09-10 2026-10-15","08:30","PPI",BLS_P)
add("2026-11-13 2026-12-15","08:30","PPI",BLS_PS)
add("2023-11-15 2023-12-14 2024-01-17 2024-02-15 2024-03-14 2024-04-15 2024-05-15 2024-06-18 2024-07-16 2024-08-15 2024-09-17 2024-10-17 2024-11-15 2024-12-17 2025-01-16 2025-02-14 2025-03-17 2025-04-16 2025-05-15 2025-06-17 2025-07-17 2025-08-15 2025-09-16 2025-11-25 2025-12-16 2026-01-14 2026-02-10 2026-03-06 2026-04-01 2026-05-14 2026-06-17 2026-07-16 2026-08-14 2026-09-16 2026-10-15","08:30","RETAIL_SALES",ALF)
add("2026-11-17 2026-12-16","08:30","RETAIL_SALES",CEN)
add("2023-10-26 2023-11-29 2023-12-21","08:30","GDP",BEA23); add("2023-10-27 2023-11-30 2023-12-22","08:30","PCE",BEA23)
add("2024-01-25 2024-02-28 2024-03-28 2024-04-25 2024-05-30 2024-06-27 2024-07-25 2024-08-29 2024-09-26 2024-10-30 2024-11-27 2024-12-19","08:30","GDP",BEA24)
add("2024-01-26 2024-02-29 2024-03-29 2024-04-26 2024-05-31 2024-06-28 2024-07-26 2024-08-30 2024-09-27 2024-10-31 2024-11-27 2024-12-20","08:30","PCE",BEA24)
add("2025-01-30 2025-02-27 2025-03-27 2025-04-30 2025-05-29 2025-06-26 2025-07-30 2025-08-28 2025-09-25 2025-12-23","08:30","GDP",BEA25)
add("2025-01-31 2025-02-28 2025-03-28 2025-04-30 2025-05-30 2025-06-27 2025-07-31 2025-08-29 2025-09-26 2025-12-05","08:30","PCE",BEA25)
add("2026-01-22 2026-02-20 2026-03-13 2026-04-09 2026-04-30 2026-05-28 2026-06-25 2026-07-30 2026-08-26 2026-09-30 2026-10-29 2026-11-25 2026-12-23","08:30","GDP",BEA26)
add("2026-01-22 2026-02-20 2026-03-13 2026-04-09 2026-04-30 2026-05-28 2026-06-25 2026-07-30 2026-08-26 2026-09-30 2026-10-29 2026-11-25 2026-12-23","08:30","PCE",BEA26)
for y,m in [(2023,11),(2023,12)]+[(y,m) for y in (2024,2025) for m in range(1,13)]:
    mf,sv=ism(y,m); rows.append((str(mf),"10:00","ISM_MANUFACTURING",ISMR)); rows.append((str(sv),"10:00","ISM_SERVICES",ISMR))
for m,(mf,sv) in official2026.items():
    rows.append((mf,"10:00","ISM_MANUFACTURING",ISMO)); rows.append((sv,"10:00","ISM_SERVICES",ISMO))
rows.sort()
assert len(rows)==len(set(rows))
with open("usd_high_impact.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["date_et","time_et","event","source"]); w.writerows(rows)
import collections
days=sorted({r[0] for r in rows}); print("events",len(rows),"distinct days",len(days),"range",days[0],days[-1])
c=collections.Counter(r[2] for r in rows); print(dict(c))
