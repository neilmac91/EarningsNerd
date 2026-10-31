# Restatement census (WP5 §5a)

Run 2026-10-25T09:33:15.210903Z. Companyfacts through `app.services.facts.transport` (shared limiter, Settings SEC identity). 60 tickers requested, 59 measured, 8616 cells (company x concept x fiscal year, newest 10 fiscal years, FY durations and FY-end instants).

Definitions: *winner* = the value ingest stores (latest-filed item of the first tag with data). *own* = the item from the year's own annual report (ANNUAL_FORMS, `own_period_ends` == this period end; earliest filed, non-amended first). *within* = own looked up in the winning tag only; *across* = own looked up in all the concept's tags (the own filing's value under its highest-priority tag). *later filing* = own found and its accession differs from the winner's. Gap = |winner - own| / |own|.

## Coverage

| ticker | CIK | entity | financial SIC | fiscal years | cells | note |
|---|---|---|---|---|---|---|
| REGN | 0000872589 | REGENERON PHARMACEUTICALS, INC. | False | 2016-2025 | 147 |  |
| AAPL | 0000320193 | Apple Inc. | False | 2016-2025 | 160 |  |
| MSFT | 0000789019 | Microsoft Corporation | False | 2017-2026 | 160 |  |
| AMZN | 0001018724 | AMAZON COM INC | False | 2016-2025 | 150 |  |
| JPM | 0000019617 | JPMORGAN CHASE & CO | True | 2016-2025 | 110 |  |
| BAC | 0000070858 | BofA Finance LLC | True | 2016-2025 | 120 |  |
| XOM | 0002115436 | ExxonMobil Holdings Corp | False |  | 0 |  |
| CVX | 0000093410 | Chevron Corp | False | 2016-2025 | 136 |  |
| JNJ | 0000200406 | Johnson & Johnson | False | 2016-2025 | 150 |  |
| PFE | 0000078003 | PFIZER INC | False | 2016-2025 | 140 |  |
| LLY | 0000059478 | ELI LILLY AND COMPANY | False | 2016-2025 | 130 |  |
| MRK | 0000310158 | Merck & Co., Inc. | False | 2016-2025 | 140 |  |
| ABBV | 0001551152 | AbbVie Inc. | False | 2016-2025 | 147 |  |
| KO | 0000021344 | COCA COLA CO | False | 2016-2025 | 158 |  |
| PEP | 0000077476 | PEPSICO INC | False | 2016-2025 | 160 |  |
| PG | 0000080424 | PROCTER & GAMBLE CO | False | 2017-2026 | 150 |  |
| WMT | 0000104169 | Walmart Inc. | False | 2017-2026 | 158 |  |
| COST | 0000909832 | COSTCO WHOLESALE CORP /NEW | False | 2017-2026 | 151 |  |
| HD | 0000354950 | The Home Depot, Inc. | False | 2016-2025 | 157 |  |
| NKE | 0000320187 | NIKE, Inc. | False | 2017-2026 | 150 |  |
| MCD | 0000063908 | McDONALD’S CORPORATION | False | 2016-2025 | 150 |  |
| DIS | 0001744489 | WALT DISNEY CO/ | False | 2017-2025 | 135 |  |
| NFLX | 0001065280 | Netflix, Inc. | False | 2016-2025 | 150 |  |
| GOOGL | 0001652044 | Alphabet Inc. | False | 2016-2025 | 150 |  |
| META | 0001326801 | Meta Platforms, Inc. | False | 2016-2025 | 145 |  |
| NVDA | 0001045810 | NVIDIA CORP | False | 2017-2026 | 155 |  |
| INTC | 0000050863 | INTEL CORP | False | 2016-2025 | 160 |  |
| AMD | 0000002488 | ADVANCED MICRO DEVICES INC | False | 2016-2025 | 170 |  |
| CSCO | 0000858877 | CISCO SYSTEMS, INC. | False | 2017-2026 | 160 |  |
| ORCL | 0001341439 | Oracle Corporation | False | 2017-2026 | 143 |  |
| IBM | 0000051143 | INTERNATIONAL BUSINESS MACHINES CORPORATION | False | 2016-2025 | 150 |  |
| CAT | 0000018230 | CATERPILLAR INC | False | 2016-2025 | 150 |  |
| DE | 0000315189 | DEERE & CO | False | 2016-2025 | 140 |  |
| GE | 0000040545 | GENERAL ELECTRIC COMPANY | False | 2016-2025 | 127 |  |
| HON | 0000773840 | Honeywell International Inc | False | 2016-2025 | 149 |  |
| BA | 0000012927 | THE BOEING COMPANY | False | 2016-2025 | 157 |  |
| LMT | 0000936468 | LOCKHEED MARTIN CORPORATION | False | 2016-2025 | 160 |  |
| UNH | 0000731766 | UnitedHealth Group Incorporated | True | 2016-2025 | 150 |  |
| CVS | 0000064803 | CVS HEALTH CORPORATION | False | 2016-2025 | 170 | CIK via resolve_ticker; SIC unknown, read as non-financial.  |
| T | 0000732717 | AT&T INC. | False | 2016-2025 | 147 |  |
| VZ | 0000732712 | VERIZON COMMUNICATIONS INC | False | 2016-2025 | 133 |  |
| UPS | 0001090727 | UNITED PARCEL SERVICE INC | False | 2016-2025 | 150 |  |
| FDX | 0001048911 | FEDEX CORP | False | 2017-2026 | 150 |  |
| NEE | 0000753308 | NEXTERA ENERGY INC | False | 2016-2025 | 138 |  |
| DUK | 0001326160 | Duke Energy CORP | False | 2016-2025 | 149 | CIK via resolve_ticker; SIC unknown, read as non-financial.  |
| SPG | 0001063761 | SIMON PROPERTY GROUP, INC. | True | 2016-2025 | 120 |  |
| PLD | 0001045609 | Prologis, Inc. | True | 2016-2025 | 110 |  |
| GS | 0000886982 | The Goldman Sachs Group, Inc. | True | 2016-2025 | 123 |  |
| MS | 0000895421 | MORGAN STANLEY | True | 2016-2025 | 120 |  |
| AXP | 0000004962 | AMERICAN EXPRESS COMPANY | True | 2016-2025 | 124 |  |
| V | 0001403161 | VISA INC. | False | 2016-2025 | 138 |  |
| MA | 0001141391 | Mastercard Incorporated | False | 2016-2025 | 150 |  |
| TSLA | 0001318605 | Tesla, Inc. | False | 2016-2025 | 160 |  |
| F | 0000037996 | Ford Motor Co | False | 2016-2025 | 142 | CIK via resolve_ticker; SIC unknown, read as non-financial.  |
| GM | 0001467858 | GENERAL MOTORS COMPANY | False | 2016-2025 | 140 |  |
| SBUX | 0000829224 | Starbucks Corporation | False | 2016-2025 | 150 |  |
| TGT | 0000027419 | Target Corporation | False | 2016-2025 | 152 |  |
| LOW | 0000060667 | LOWES COMPANIES INC | False | 2016-2025 | 155 |  |
| ADBE | 0000796343 | ADOBE INC. | False | 2016-2025 | 160 |  |
| CRM | 0001108524 | Salesforce, Inc. | False | 2017-2026 | 160 |  |

## Forms the shown value comes from

| form | cells | cells with a gap > 1% |
|---|---|---|
| 10-K | 7882 | 391 |
| 10-Q | 381 | 5 |
| 8-K | 208 | 25 |
| DEF 14A | 115 | 16 |
| 10-K/A | 25 | 1 |
| PRE 14C | 5 | 0 |

Cells whose shown value comes from a proxy statement (120):

- AMZN net_income FY2021: shown 33,364.0M USD (DEF 14A 0001104659-26-041026 filed 2026-04-09); own 33,364.0M USD (10-K 0001018724-22-000005)
- AMZN net_income FY2022: shown -2,722.0M USD (DEF 14A 0001104659-26-041026 filed 2026-04-09); own -2,722.0M USD (10-K 0001018724-23-000004)
- AMZN net_income FY2023: shown 30,425.0M USD (DEF 14A 0001104659-26-041026 filed 2026-04-09); own 30,425.0M USD (10-K 0001018724-24-000008)
- AMZN net_income FY2024: shown 59,248.0M USD (DEF 14A 0001104659-26-041026 filed 2026-04-09); own 59,248.0M USD (10-K 0001018724-25-000004)
- AMZN net_income FY2025: shown 77,670.0M USD (DEF 14A 0001104659-26-041026 filed 2026-04-09); own 77,670.0M USD (10-K 0001018724-26-000004)
- CAT net_income FY2021: shown 6,489.0M USD (DEF 14A 0001308179-26-000358 filed 2026-04-30); own 6,493.0M USD (10-K 0000018230-22-000050)
- CAT net_income FY2022: shown 6,705.0M USD (DEF 14A 0001308179-26-000358 filed 2026-04-30); own 6,704.0M USD (10-K 0000018230-23-000011)
- CAT net_income FY2023: shown 10,335.0M USD (DEF 14A 0001308179-26-000358 filed 2026-04-30); own 10,332.0M USD (10-K 0000018230-24-000009)
- CAT net_income FY2024: shown 10,792.0M USD (DEF 14A 0001308179-26-000358 filed 2026-04-30); own 10,788.0M USD (10-K 0000018230-25-000008)
- CAT net_income FY2025: shown 8,884.0M USD (DEF 14A 0001308179-26-000358 filed 2026-04-30); own 8,882.0M USD (10-K 0000018230-26-000008)
- CRM net_income FY2022: shown 1,444.0M USD (DEF 14A 0001108524-26-000085 filed 2026-04-16); own 1,444.0M USD (10-K 0001108524-22-000013)
- CRM net_income FY2023: shown 208.0M USD (DEF 14A 0001108524-26-000085 filed 2026-04-16); own 208.0M USD (10-K 0001108524-23-000011)
- CRM net_income FY2024: shown 4,136.0M USD (DEF 14A 0001108524-26-000085 filed 2026-04-16); own 4,136.0M USD (10-K 0001108524-24-000005)
- CRM net_income FY2025: shown 6,197.0M USD (DEF 14A 0001108524-26-000085 filed 2026-04-16); own 6,197.0M USD (10-K 0001108524-25-000006)
- CRM net_income FY2026: shown 7,457.0M USD (DEF 14A 0001108524-26-000085 filed 2026-04-16); own 7,457.0M USD (10-K 0001108524-26-000060)
- CVX net_income FY2021: shown 15,600.0M USD (DEF 14A 0001193125-26-145617 filed 2026-04-07); own 15,625.0M USD (10-K 0000093410-22-000019)
- CVX net_income FY2022: shown 35,500.0M USD (DEF 14A 0001193125-26-145617 filed 2026-04-07); own 35,465.0M USD (10-K 0000093410-23-000009)
- CVX net_income FY2023: shown 21,400.0M USD (DEF 14A 0001193125-26-145617 filed 2026-04-07); own 21,369.0M USD (10-K 0000093410-24-000013)
- CVX net_income FY2024: shown 17,700.0M USD (DEF 14A 0001193125-26-145617 filed 2026-04-07); own 17,661.0M USD (10-K 0000093410-25-000009)
- CVX net_income FY2025: shown 12,300.0M USD (DEF 14A 0001193125-26-145617 filed 2026-04-07); own 12,299.0M USD (10-K 0000093410-26-000078)
- FDX net_income FY2022: shown 3,826 USD (DEF 14A 0001104659-26-097836 filed 2026-08-17); own 3,826.0M USD (10-K 0000950170-22-012762)
- FDX net_income FY2023: shown 3,972 USD (DEF 14A 0001104659-26-097836 filed 2026-08-17); own 3,972.0M USD (10-K 0000950170-23-033201)
- FDX net_income FY2024: shown 4,331 USD (DEF 14A 0001104659-26-097836 filed 2026-08-17); own 4,331.0M USD (10-K 0000950170-24-083577)
- FDX net_income FY2025: shown 4,092 USD (DEF 14A 0001104659-26-097836 filed 2026-08-17); own 4,092.0M USD (10-K 0001048911-25-000011)
- FDX net_income FY2026: shown 4,433 USD (DEF 14A 0001104659-26-097836 filed 2026-08-17); own 4,433.0M USD (10-K 0001048911-26-000105)
- GM net_income FY2021: shown 9,945.0M USD (DEF 14A 0001467858-26-000022 filed 2026-04-20); own 10,019.0M USD (10-K 0001467858-22-000034)
- GM net_income FY2022: shown 9,708.0M USD (DEF 14A 0001467858-26-000022 filed 2026-04-20); own 9,934.0M USD (10-K 0001467858-23-000029)
- GM net_income FY2023: shown 9,840.0M USD (DEF 14A 0001467858-26-000022 filed 2026-04-20); own 10,127.0M USD (10-K 0001467858-24-000031)
- GM net_income FY2024: shown 5,963.0M USD (DEF 14A 0001467858-26-000022 filed 2026-04-20); own 6,008.0M USD (10-K 0001467858-25-000032)
- GM net_income FY2025: shown 2,780.0M USD (DEF 14A 0001467858-26-000022 filed 2026-04-20); own 2,697.0M USD (10-K 0001467858-26-000013)
- GOOGL net_income FY2021: shown 76,033.0M USD (DEF 14A 0001308179-26-000342 filed 2026-04-24); own 76,033.0M USD (10-K 0001652044-22-000019)
- GOOGL net_income FY2022: shown 59,972.0M USD (DEF 14A 0001308179-26-000342 filed 2026-04-24); own 59,972.0M USD (10-K 0001652044-23-000016)
- GOOGL net_income FY2023: shown 73,795.0M USD (DEF 14A 0001308179-26-000342 filed 2026-04-24); own 73,795.0M USD (10-K 0001652044-24-000022)
- GOOGL net_income FY2024: shown 100,118.0M USD (DEF 14A 0001308179-26-000342 filed 2026-04-24); own 100,118.0M USD (10-K 0001652044-25-000014)
- GOOGL net_income FY2025: shown 132,170.0M USD (DEF 14A 0001308179-26-000342 filed 2026-04-24); own 132,170.0M USD (10-K 0001652044-26-000018)
- HD net_income FY2021: shown 16,430.0M USD (DEF 14A 0000354950-26-000090 filed 2026-04-07); own 16,433.0M USD (10-K 0000354950-22-000070)
- HD net_income FY2022: shown 17,110.0M USD (DEF 14A 0000354950-26-000090 filed 2026-04-07); own 17,105.0M USD (10-K 0000354950-23-000059)
- HD net_income FY2023: shown 15,140.0M USD (DEF 14A 0000354950-26-000090 filed 2026-04-07); own 15,143.0M USD (10-K 0000354950-24-000062)
- HD net_income FY2024: shown 14,810.0M USD (DEF 14A 0000354950-26-000090 filed 2026-04-07); own 14,806.0M USD (10-K 0000354950-25-000085)
- HD net_income FY2025: shown 14,160.0M USD (DEF 14A 0000354950-26-000090 filed 2026-04-07); own 14,156.0M USD (10-K 0001628280-26-019436)
- JPM net_income FY2021: shown 48,300.0M USD (DEF 14A 0000019617-26-000096 filed 2026-04-06); own 48,334.0M USD (10-K 0000019617-22-000272)
- JPM net_income FY2022: shown 37,700.0M USD (DEF 14A 0000019617-26-000096 filed 2026-04-06); own 37,676.0M USD (10-K 0000019617-23-000231)
- JPM net_income FY2023: shown 49,600.0M USD (DEF 14A 0000019617-26-000096 filed 2026-04-06); own 49,552.0M USD (10-K 0000019617-24-000225)
- JPM net_income FY2024: shown 58,500.0M USD (DEF 14A 0000019617-26-000096 filed 2026-04-06); own 58,471.0M USD (10-K 0000019617-25-000270)
- JPM net_income FY2025: shown 57,000.0M USD (DEF 14A 0000019617-26-000096 filed 2026-04-06); own 57,048.0M USD (10-K 0001628280-26-008131)
- LOW net_income FY2021: shown 8,442.0M USD (DEF 14A 0000060667-26-000056 filed 2026-04-16); own 8,442.0M USD (10-K 0000060667-22-000038)
- LOW net_income FY2022: shown 6,437.0M USD (DEF 14A 0000060667-26-000056 filed 2026-04-16); own 6,437.0M USD (10-K 0000060667-23-000034)
- LOW net_income FY2023: shown 7,726.0M USD (DEF 14A 0000060667-26-000056 filed 2026-04-16); own 7,726.0M USD (10-K 0000060667-24-000033)
- LOW net_income FY2024: shown 6,957.0M USD (DEF 14A 0000060667-26-000056 filed 2026-04-16); own 6,957.0M USD (10-K 0000060667-25-000049)
- LOW net_income FY2025: shown 6,654.0M USD (DEF 14A 0000060667-26-000056 filed 2026-04-16); own 6,654.0M USD (10-K 0000060667-26-000029)
- MA net_income FY2021: shown 8,687.0M USD (DEF 14A 0001141391-26-000021 filed 2026-04-27); own 8,687.0M USD (10-K 0001141391-22-000023)
- MA net_income FY2022: shown 9,930.0M USD (DEF 14A 0001141391-26-000021 filed 2026-04-27); own 9,930.0M USD (10-K 0001141391-23-000020)
- MA net_income FY2023: shown 11,195.0M USD (DEF 14A 0001141391-26-000021 filed 2026-04-27); own 11,195.0M USD (10-K 0001141391-24-000022)
- MA net_income FY2024: shown 12,874.0M USD (DEF 14A 0001141391-26-000021 filed 2026-04-27); own 12,874.0M USD (10-K 0001141391-25-000011)
- MA net_income FY2025: shown 14,968.0M USD (DEF 14A 0001141391-26-000021 filed 2026-04-27); own 14,968.0M USD (10-K 0001141391-26-000013)
- MCD net_income FY2021: shown 7,545.0M USD (DEF 14A 0001193125-26-145548 filed 2026-04-07); own 7,545.2M USD (10-K 0000063908-22-000011)
- MCD net_income FY2022: shown 6,177.0M USD (DEF 14A 0001193125-26-145548 filed 2026-04-07); own 6,177.4M USD (10-K 0000063908-23-000012)
- MCD net_income FY2023: shown 8,469.0M USD (DEF 14A 0001193125-26-145548 filed 2026-04-07); own 8,468.8M USD (10-K 0000063908-24-000072)
- MCD net_income FY2024: shown 8,223.0M USD (DEF 14A 0001193125-26-145548 filed 2026-04-07); own 8,223.0M USD (10-K 0000063908-25-000012)
- MCD net_income FY2025: shown 8,563.0M USD (DEF 14A 0001193125-26-145548 filed 2026-04-07); own 8,563.0M USD (10-K 0000063908-26-000035)
- META net_income FY2021: shown 39,370.0M USD (PRE 14C 0001628280-26-066710 filed 2026-10-21); own 39,370.0M USD (10-K 0001326801-22-000018)
- META net_income FY2022: shown 23,200.0M USD (PRE 14C 0001628280-26-066710 filed 2026-10-21); own 23,200.0M USD (10-K 0001326801-23-000013)
- META net_income FY2023: shown 39,098.0M USD (PRE 14C 0001628280-26-066710 filed 2026-10-21); own 39,098.0M USD (10-K 0001326801-24-000012)
- META net_income FY2024: shown 62,360.0M USD (PRE 14C 0001628280-26-066710 filed 2026-10-21); own 62,360.0M USD (10-K 0001326801-25-000017)
- META net_income FY2025: shown 60,458.0M USD (PRE 14C 0001628280-26-066710 filed 2026-10-21); own 60,458.0M USD (10-K 0001628280-26-003942)
- MRK net_income FY2021: shown 12,345.0M USD (DEF 14A 0001193125-26-147704 filed 2026-04-08); own 13,049.0M USD (10-K 0000310158-22-000003)
- MRK net_income FY2022: shown 14,519.0M USD (DEF 14A 0001193125-26-147704 filed 2026-04-08); own 14,519.0M USD (10-K 0001628280-23-005061)
- MRK net_income FY2023: shown 365.0M USD (DEF 14A 0001193125-26-147704 filed 2026-04-08); own 365.0M USD (10-K 0001628280-24-006850)
- MRK net_income FY2024: shown 17,117.0M USD (DEF 14A 0001193125-26-147704 filed 2026-04-08); own 17,117.0M USD (10-K 0001628280-25-007732)
- MRK net_income FY2025: shown 18,254.0M USD (DEF 14A 0001193125-26-147704 filed 2026-04-08); own 18,254.0M USD (10-K 0000310158-26-000063)
- MSFT net_income FY2022: shown 72,738.0M USD (DEF 14A 0001193125-26-427849 filed 2026-10-21); own 72,738.0M USD (10-K 0001564590-22-026876)
- MSFT net_income FY2023: shown 72,361.0M USD (DEF 14A 0001193125-26-427849 filed 2026-10-21); own 72,361.0M USD (10-K 0000950170-23-035122)
- MSFT net_income FY2024: shown 88,136.0M USD (DEF 14A 0001193125-26-427849 filed 2026-10-21); own 88,136.0M USD (10-K 0000950170-24-087843)
- MSFT net_income FY2025: shown 101,832.0M USD (DEF 14A 0001193125-26-427849 filed 2026-10-21); own 101,832.0M USD (10-K 0000950170-25-100235)
- MSFT net_income FY2026: shown 133,749.0M USD (DEF 14A 0001193125-26-427849 filed 2026-10-21); own 133,749.0M USD (10-K 0001193125-26-323660)
- NFLX net_income FY2021: shown 5,116.0M USD (DEF 14A 0001193125-26-159286 filed 2026-04-16); own 5,116.2M USD (10-K 0001065280-22-000036)
- NFLX net_income FY2022: shown 4,492.0M USD (DEF 14A 0001193125-26-159286 filed 2026-04-16); own 4,491.9M USD (10-K 0001065280-23-000035)
- NFLX net_income FY2023: shown 5,408.0M USD (DEF 14A 0001193125-26-159286 filed 2026-04-16); own 5,408.0M USD (10-K 0001065280-24-000030)
- NFLX net_income FY2024: shown 8,712.0M USD (DEF 14A 0001193125-26-159286 filed 2026-04-16); own 8,711.6M USD (10-K 0001065280-25-000044)
- NFLX net_income FY2025: shown 10,981.0M USD (DEF 14A 0001193125-26-159286 filed 2026-04-16); own 10,981.2M USD (10-K 0001065280-26-000034)
- NKE net_income FY2022: shown 6,046.0M USD (DEF 14A 0000320187-26-000089 filed 2026-07-15); own 6,046.0M USD (10-K 0000320187-22-000038)
- NKE net_income FY2023: shown 5,070.0M USD (DEF 14A 0000320187-26-000089 filed 2026-07-15); own 5,070.0M USD (10-K 0000320187-23-000039)
- NKE net_income FY2024: shown 5,700.0M USD (DEF 14A 0000320187-26-000089 filed 2026-07-15); own 5,700.0M USD (10-K 0000320187-24-000044)
- NKE net_income FY2025: shown 3,219.0M USD (DEF 14A 0000320187-26-000089 filed 2026-07-15); own 3,219.0M USD (10-K 0000320187-25-000047)
- NKE net_income FY2026: shown 3,108.0M USD (DEF 14A 0000320187-26-000089 filed 2026-07-15); own 3,108.0M USD (10-K 0000320187-26-000088)
- NVDA net_income FY2022: shown 9,752.0M USD (DEF 14A 0001045810-26-000036 filed 2026-05-12); own 9,752.0M USD (10-K 0001045810-22-000036)
- NVDA net_income FY2023: shown 4,368.0M USD (DEF 14A 0001045810-26-000036 filed 2026-05-12); own 4,368.0M USD (10-K 0001045810-23-000017)
- NVDA net_income FY2024: shown 29,760.0M USD (DEF 14A 0001045810-26-000036 filed 2026-05-12); own 29,760.0M USD (10-K 0001045810-24-000029)
- NVDA net_income FY2025: shown 72,880.0M USD (DEF 14A 0001045810-26-000036 filed 2026-05-12); own 72,880.0M USD (10-K 0001045810-25-000023)
- NVDA net_income FY2026: shown 120,067.0M USD (DEF 14A 0001045810-26-000036 filed 2026-05-12); own 120,067.0M USD (10-K 0001045810-26-000021)
- ORCL net_income FY2022: shown 6,717.0M USD (DEF 14A 0001193125-26-402816 filed 2026-09-25); own 6,717.0M USD (10-K 0001564590-22-023675)
- ORCL net_income FY2023: shown 8,503.0M USD (DEF 14A 0001193125-26-402816 filed 2026-09-25); own 8,503.0M USD (10-K 0000950170-23-028914)
- ORCL net_income FY2024: shown 10,467.0M USD (DEF 14A 0001193125-26-402816 filed 2026-09-25); own 10,467.0M USD (10-K 0000950170-24-075605)
- ORCL net_income FY2025: shown 12,443.0M USD (DEF 14A 0001193125-26-402816 filed 2026-09-25); own 12,443.0M USD (10-K 0000950170-25-087926)
- ORCL net_income FY2026: shown 16,984.0M USD (DEF 14A 0001193125-26-402816 filed 2026-09-25); own 17,087.0M USD (10-K 0001193125-26-277521)
- REGN net_income FY2021: shown 8,075.3M USD (DEF 14A 0001308179-26-000340 filed 2026-04-24); own 8,075.3M USD (10-K 0001804220-22-000007)
- REGN net_income FY2022: shown 4,338.4M USD (DEF 14A 0001308179-26-000340 filed 2026-04-24); own 4,338.4M USD (10-K 0001804220-23-000008)
- REGN net_income FY2023: shown 3,953.6M USD (DEF 14A 0001308179-26-000340 filed 2026-04-24); own 3,953.6M USD (10-K 0001804220-24-000009)
- REGN net_income FY2024: shown 4,412.6M USD (DEF 14A 0001308179-26-000340 filed 2026-04-24); own 4,412.6M USD (10-K 0001804220-25-000011)
- REGN net_income FY2025: shown 4,504.9M USD (DEF 14A 0001308179-26-000340 filed 2026-04-24); own 4,504.9M USD (10-K 0000872589-26-000008)
- TGT net_income FY2021: shown 6,946.0M USD (DEF 14A 0001628280-26-027508 filed 2026-04-27); own 6,946.0M USD (10-K 0000027419-22-000007)
- TGT net_income FY2022: shown 2,780.0M USD (DEF 14A 0001628280-26-027508 filed 2026-04-27); own 2,780.0M USD (10-K 0000027419-23-000015)
- TGT net_income FY2023: shown 4,138.0M USD (DEF 14A 0001628280-26-027508 filed 2026-04-27); own 4,138.0M USD (10-K 0000027419-24-000032)
- TGT net_income FY2024: shown 4,091.0M USD (DEF 14A 0001628280-26-027508 filed 2026-04-27); own 4,091.0M USD (10-K 0000027419-25-000018)
- TGT net_income FY2025: shown 3,705.0M USD (DEF 14A 0001628280-26-027508 filed 2026-04-27); own 3,705.0M USD (10-K 0000027419-26-000016)
- TSLA net_income FY2021: shown 5,644.0M USD (DEF 14A 0001104659-26-116700 filed 2026-10-19); own 5,519.0M USD (10-K 0000950170-22-000796)
- TSLA net_income FY2022: shown 12,587.0M USD (DEF 14A 0001104659-26-116700 filed 2026-10-19); own 12,556.0M USD (10-K 0000950170-23-001409)
- TSLA net_income FY2023: shown 14,974.0M USD (DEF 14A 0001104659-26-116700 filed 2026-10-19); own 14,997.0M USD (10-K 0001628280-24-002390)
- TSLA net_income FY2024: shown 7,153.0M USD (DEF 14A 0001104659-26-116700 filed 2026-10-19); own 7,091.0M USD (10-K 0001628280-25-003063)
- TSLA net_income FY2025: shown 3,855.0M USD (DEF 14A 0001104659-26-116700 filed 2026-10-19); own 3,794.0M USD (10-K 0001628280-26-003952)
- VZ net_income FY2021: shown 22,618.0M USD (DEF 14A 0001308179-26-000210 filed 2026-04-06); own 22,065.0M USD (10-K 0000732712-22-000008)
- VZ net_income FY2022: shown 21,748.0M USD (DEF 14A 0001308179-26-000210 filed 2026-04-06); own 21,256.0M USD (10-K 0000732712-23-000012)
- VZ net_income FY2023: shown 12,095.0M USD (DEF 14A 0001308179-26-000210 filed 2026-04-06); own 11,614.0M USD (10-K 0000732712-24-000010)
- VZ net_income FY2024: shown 17,949.0M USD (DEF 14A 0001308179-26-000210 filed 2026-04-06); own 17,506.0M USD (10-K 0000732712-25-000006)
- VZ net_income FY2025: shown 17,608.0M USD (DEF 14A 0001308179-26-000210 filed 2026-04-06); own 17,174.0M USD (10-K 0000732712-26-000007)
- WMT net_income FY2022: shown 13,673.0M USD (DEF 14A 0001193125-26-173673 filed 2026-04-23); own 13,673.0M USD (10-K 0000104169-22-000012)
- WMT net_income FY2023: shown 11,680.0M USD (DEF 14A 0001193125-26-173673 filed 2026-04-23); own 11,680.0M USD (10-K 0000104169-23-000020)
- WMT net_income FY2024: shown 15,511.0M USD (DEF 14A 0001193125-26-173673 filed 2026-04-23); own 15,511.0M USD (10-K 0000104169-24-000056)
- WMT net_income FY2025: shown 19,436.0M USD (DEF 14A 0001193125-26-173673 filed 2026-04-23); own 19,436.0M USD (10-K 0000104169-25-000021)
- WMT net_income FY2026: shown 21,893.0M USD (DEF 14A 0001193125-26-173673 filed 2026-04-23); own 21,893.0M USD (10-K 0000104169-26-000055)

## Size: own differs from winner (own looked up across all the concept's tags)

Each tolerance column: cells (companies) whose gap exceeds it.

| concept | measured | own found | later filing | > 0.1% | > 0.5% | > 1% | > 2% | > 5% |
|---|---|---|---|---|---|---|---|---|
| capital_expenditures | 518 | 512 | 458 | 28 (10) | 24 (8) | 21 (7) | 19 (7) | 15 (7) |
| cash_and_equivalents | 590 | 582 | 575 | 28 (15) | 23 (12) | 22 (11) | 17 (10) | 13 (8) |
| current_assets | 506 | 503 | 499 | 19 (15) | 14 (10) | 13 (9) | 10 (6) | 7 (4) |
| current_liabilities | 506 | 503 | 499 | 19 (13) | 16 (11) | 13 (9) | 8 (5) | 6 (4) |
| earnings_per_share | 577 | 568 | 508 | 50 (22) | 46 (21) | 42 (19) | 38 (18) | 31 (14) |
| eps_diluted | 577 | 566 | 505 | 50 (23) | 47 (22) | 43 (20) | 38 (18) | 31 (14) |
| financing_cash_flow | 590 | 587 | 525 | 50 (30) | 38 (25) | 30 (19) | 22 (17) | 11 (10) |
| gross_profit | 192 | 192 | 169 | 26 (12) | 22 (11) | 17 (10) | 12 (8) | 8 (5) |
| investing_cash_flow | 590 | 587 | 525 | 60 (28) | 41 (21) | 35 (18) | 30 (15) | 15 (11) |
| long_term_debt | 488 | 473 | 422 | 12 (11) | 10 (9) | 8 (7) | 5 (5) | 4 (4) |
| net_income | 590 | 586 | 549 | 59 (22) | 45 (19) | 37 (16) | 31 (16) | 16 (9) |
| net_interest_income | 81 | 80 | 71 | 6 (3) | 4 (2) | 4 (2) | 2 (1) | 2 (1) |
| net_investment_income | 10 | 8 | 7 | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 0 (0) |
| noninterest_income | 50 | 50 | 45 | 15 (5) | 12 (5) | 10 (5) | 7 (4) | 4 (2) |
| operating_cash_flow | 590 | 587 | 525 | 66 (34) | 54 (29) | 40 (19) | 31 (16) | 20 (8) |
| operating_income | 452 | 443 | 396 | 55 (26) | 44 (24) | 38 (22) | 34 (22) | 20 (14) |
| premiums_earned | 22 | 20 | 16 | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 0 (0) |
| revenue | 507 | 495 | 434 | 50 (22) | 49 (22) | 42 (19) | 32 (13) | 31 (12) |
| shareholders_equity | 590 | 587 | 582 | 27 (17) | 20 (14) | 14 (9) | 12 (7) | 10 (6) |
| total_assets | 590 | 587 | 582 | 29 (15) | 14 (8) | 9 (5) | 7 (5) | 2 (2) |
| **all (59 cos)** | 8616 | 8516 | 7892 | 649 (57) | 523 (55) | 438 (52) | 355 (49) | 246 (44) |

## Size: own differs from winner (own looked up within the winning tag only)

Each tolerance column: cells (companies) whose gap exceeds it.

| concept | measured | own found | later filing | > 0.1% | > 0.5% | > 1% | > 2% | > 5% |
|---|---|---|---|---|---|---|---|---|
| capital_expenditures | 518 | 508 | 454 | 28 (10) | 24 (8) | 21 (7) | 19 (7) | 15 (7) |
| cash_and_equivalents | 590 | 572 | 565 | 24 (13) | 19 (10) | 18 (9) | 14 (8) | 11 (7) |
| current_assets | 506 | 503 | 499 | 19 (15) | 14 (10) | 13 (9) | 10 (6) | 7 (4) |
| current_liabilities | 506 | 503 | 499 | 19 (13) | 16 (11) | 13 (9) | 8 (5) | 6 (4) |
| earnings_per_share | 577 | 563 | 503 | 50 (22) | 46 (21) | 42 (19) | 38 (18) | 31 (14) |
| eps_diluted | 577 | 563 | 502 | 50 (23) | 47 (22) | 43 (20) | 38 (18) | 31 (14) |
| financing_cash_flow | 590 | 552 | 490 | 43 (26) | 34 (22) | 28 (18) | 21 (16) | 10 (9) |
| gross_profit | 192 | 192 | 169 | 26 (12) | 22 (11) | 17 (10) | 12 (8) | 8 (5) |
| investing_cash_flow | 590 | 552 | 490 | 50 (25) | 33 (18) | 29 (16) | 25 (13) | 12 (10) |
| long_term_debt | 488 | 466 | 415 | 10 (9) | 8 (7) | 6 (5) | 3 (3) | 3 (3) |
| net_income | 590 | 571 | 534 | 57 (22) | 44 (19) | 36 (16) | 30 (15) | 15 (8) |
| net_interest_income | 81 | 80 | 71 | 6 (3) | 4 (2) | 4 (2) | 2 (1) | 2 (1) |
| net_investment_income | 10 | 8 | 7 | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 0 (0) |
| noninterest_income | 50 | 50 | 45 | 15 (5) | 12 (5) | 10 (5) | 7 (4) | 4 (2) |
| operating_cash_flow | 590 | 552 | 490 | 58 (30) | 47 (26) | 35 (17) | 26 (14) | 15 (6) |
| operating_income | 452 | 443 | 396 | 55 (26) | 44 (24) | 38 (22) | 34 (22) | 20 (14) |
| premiums_earned | 22 | 20 | 16 | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 0 (0) |
| revenue | 507 | 426 | 365 | 31 (14) | 31 (14) | 28 (13) | 25 (11) | 25 (11) |
| shareholders_equity | 590 | 583 | 578 | 27 (17) | 20 (14) | 14 (9) | 12 (7) | 10 (6) |
| total_assets | 590 | 587 | 582 | 29 (15) | 14 (8) | 9 (5) | 7 (5) | 2 (2) |
| **all (59 cos)** | 8616 | 8294 | 7670 | 597 (57) | 479 (54) | 404 (52) | 331 (48) | 227 (42) |

## Rounding noise: relative-gap histogram (across, later-filing cells only)

| relative gap | cells | share | cumulative | rounding only | per-share |
|---|---|---|---|---|---|
| 0 (identical) | 7048 | 89.3% | 89.3% | 0 | 911 |
| (0%, 0.001%] | 24 | 0.3% | 89.6% | 24 | 0 |
| (0.001%, 0.01%] | 76 | 1.0% | 90.6% | 64 | 0 |
| (0.01%, 0.05%] | 65 | 0.8% | 91.4% | 26 | 0 |
| (0.05%, 0.1%] | 30 | 0.4% | 91.8% | 2 | 2 |
| (0.1%, 0.2%] | 54 | 0.7% | 92.5% | 3 | 3 |
| (0.2%, 0.5%] | 72 | 0.9% | 93.4% | 0 | 4 |
| (0.5%, 1%] | 85 | 1.1% | 94.5% | 1 | 8 |
| (1%, 2%] | 83 | 1.1% | 95.5% | 0 | 9 |
| (2%, 5%] | 109 | 1.4% | 96.9% | 0 | 14 |
| > 5% | 246 | 3.1% | 100.0% | 0 | 62 |

## Rounding noise: relative-gap histogram (within, later-filing cells only)

| relative gap | cells | share | cumulative | rounding only | per-share |
|---|---|---|---|---|---|
| 0 (identical) | 6889 | 89.8% | 89.8% | 0 | 903 |
| (0%, 0.001%] | 22 | 0.3% | 90.1% | 22 | 0 |
| (0.001%, 0.01%] | 75 | 1.0% | 91.1% | 63 | 0 |
| (0.01%, 0.05%] | 60 | 0.8% | 91.9% | 26 | 0 |
| (0.05%, 0.1%] | 27 | 0.4% | 92.2% | 2 | 2 |
| (0.1%, 0.2%] | 48 | 0.6% | 92.8% | 3 | 3 |
| (0.2%, 0.5%] | 70 | 0.9% | 93.8% | 0 | 4 |
| (0.5%, 1%] | 75 | 1.0% | 94.7% | 0 | 8 |
| (1%, 2%] | 73 | 1.0% | 95.7% | 0 | 9 |
| (2%, 5%] | 104 | 1.4% | 97.0% | 0 | 14 |
| > 5% | 227 | 3.0% | 100.0% | 0 | 62 |

## Tag changes

- later-filing cells (across): 7892
- own value under a different tag than the winner's: 222 (2.8%)
- own report absent from the winning tag (only an across-tag lookup finds it): 222
- own found in both lookups but they disagree (another accession or value): 0
- accessions whose own period end differs between the winning-tag and all-tag maps: 0

| tolerance | cells > tol (across) | of which own under another tag | within-tag lookup misses (no own in winning tag) | within-tag lookup finds the gap |
|---|---|---|---|---|
| 0.1% | 649 | 52 | 52 | 597 |
| 0.5% | 523 | 44 | 44 | 479 |
| 1% | 438 | 34 | 34 | 404 |
| 2% | 355 | 24 | 24 | 331 |
| 5% | 246 | 19 | 19 | 227 |

Within-tag gaps the across-tag lookup does not report (own filing used a higher-priority tag for another line, or another accession was picked):

- 0 cells > 1% within but not across: 

## Cause evidence, mechanically bucketed (across-tag own; first match wins)

A first reading from the evidence alone, not a verdict: *proxy statement* = the shown value is from a DEF 14A (pay-versus-performance) filed after the reports; *scale factor* = one value is the other times 1,000 or 1,000,000 (an XBRL scale error on one side); *exact sign flip* = one value is the other negated (an XBRL sign error on one side); *per-share split* = a per-share value off by a whole-number ratio; *re-tagged* = the later filing still reports the own value under another of the concept's tags; *isolated* = at most 2 other same-year currency lines the two filings share changed; *discontinued-operations recast* = changed lines include discontinued-operations tags; *broad recast* = more lines changed, split by whether net income moved (a restatement or a retrospective accounting change moves it; a reclassification does not).

| bucket | > 0.5% cells (cos) | > 1% cells (cos) | > 2% cells (cos) | > 5% cells (cos) |
|---|---|---|---|---|
| shown value from a proxy statement | 20 (6) | 16 (5) | 15 (5) | 6 (2) |
| scale factor of 1000^n | 1 (1) | 1 (1) | 1 (1) | 1 (1) |
| exact sign flip | 3 (2) | 3 (2) | 3 (2) | 3 (2) |
| per-share split | 42 (9) | 42 (9) | 42 (9) | 42 (9) |
| own year's amended report | 0 (0) | 0 (0) | 0 (0) | 0 (0) |
| same figure re-tagged in the later filing | 14 (8) | 12 (7) | 10 (7) | 9 (6) |
| own value under another tag of the concept | 34 (18) | 26 (15) | 17 (10) | 13 (7) |
| isolated line change | 14 (9) | 12 (7) | 8 (4) | 8 (4) |
| discontinued-operations recast | 92 (8) | 83 (8) | 72 (7) | 50 (5) |
| broad recast, net income changed | 101 (11) | 80 (11) | 65 (11) | 43 (10) |
| broad recast, net income unchanged | 202 (43) | 163 (39) | 122 (35) | 71 (23) |
| no same-year lines to compare | 0 (0) | 0 (0) | 0 (0) | 0 (0) |

Net income for the same fiscal year in the two filings (gap cells, per-share splits left out):

| tolerance | net income unchanged | net income changed | not comparable |
|---|---|---|---|
| > 0.5% | 246 | 192 | 43 |
| > 1% | 206 | 159 | 31 |
| > 2% | 166 | 131 | 16 |
| > 5% | 114 | 83 | 7 |

## Gaps over 1% whose own value sits under another tag (34)

| ticker | concept | FY | gap | own value (tag) | shown value (tag) | the later filing's value under the own tag |
|---|---|---|---|---|---|---|
| AAPL | financing_cash_flow | 2016 | 1.99% | -20,483.0M USD (NetCashProvidedByUsedInFinancingActivitiesContinuingOperations) | -20,890.0M USD (NetCashProvidedByUsedInFinancingActivities) | not reported |
| AMD | revenue | 2016 | 1.10% | 4,272.0M USD (SalesRevenueNet) | 4,319.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |
| AMD | revenue | 2017 | 1.43% | 5,329.0M USD (SalesRevenueNet) | 5,253.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |
| AXP | cash_and_equivalents | 2021 | 2.38% | 22,028.0M USD (CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents) | 21,503.0M USD (CashAndCashEquivalentsAtCarryingValue) | 22,028.0M USD |
| AXP | cash_and_equivalents | 2022 | 1.60% | 33,914.0M USD (CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents) | 33,370.0M USD (CashAndCashEquivalentsAtCarryingValue) | 33,914.0M USD |
| BAC | investing_cash_flow | 2016 | 1.36% | -63,143.0M USD (NetCashProvidedByUsedInInvestingActivitiesContinuingOperations) | -62,285.0M USD (NetCashProvidedByUsedInInvestingActivities) | not reported |
| BAC | operating_cash_flow | 2016 | 5.62% | 18,306.0M USD (NetCashProvidedByUsedInOperatingActivitiesContinuingOperations) | 17,277.0M USD (NetCashProvidedByUsedInOperatingActivities) | not reported |
| BAC | operating_cash_flow | 2017 | 5.18% | 10,403.0M USD (NetCashProvidedByUsedInOperatingActivitiesContinuingOperations) | 9,864.0M USD (NetCashProvidedByUsedInOperatingActivities) | not reported |
| CAT | investing_cash_flow | 2017 | 2.82% | -994.0M USD (NetCashProvidedByUsedInInvestingActivitiesContinuingOperations) | -966.0M USD (NetCashProvidedByUsedInInvestingActivities) | not reported |
| CVX | cash_and_equivalents | 2020 | 16.94% | 6,737.0M USD (CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents) | 5,596.0M USD (CashAndCashEquivalentsAtCarryingValue) | 6,737.0M USD |
| CVX | cash_and_equivalents | 2021 | 17.00% | 6,795.0M USD (CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents) | 5,640.0M USD (CashAndCashEquivalentsAtCarryingValue) | 6,795.0M USD |
| F | net_income | 2022 | 7.95% | -2,152.0M USD (ProfitLoss) | -1,981.0M USD (NetIncomeLoss) | -2,152.0M USD |
| FDX | long_term_debt | 2025 | 3.76% | 19,899.0M USD (LongTermDebt) | 19,151.0M USD (LongTermDebtNoncurrent) | not reported |
| GE | revenue | 2016 | 10.93% | 123,693.0M USD (Revenues) | 110,171.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | 119,469.0M USD |
| GE | revenue | 2017 | 9.11% | 122,092.0M USD (Revenues) | 110,968.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | 118,243.0M USD |
| GM | revenue | 2018 | 9.52% | 147,049.0M USD (Revenues) | 133,045.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | 147,049.0M USD |
| GM | revenue | 2019 | 10.59% | 137,237.0M USD (Revenues) | 122,697.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | 137,237.0M USD |
| GOOGL | long_term_debt | 2023 | 20.13% | 14,862.0M USD (LongTermDebt) | 11,870.0M USD (LongTermDebtNoncurrent) | 13,000.0M USD |
| GS | financing_cash_flow | 2016 | 9.89% | 13,432.0M USD (NetCashProvidedByUsedInFinancingActivitiesContinuingOperations) | 12,103.0M USD (NetCashProvidedByUsedInFinancingActivities) | not reported |
| GS | investing_cash_flow | 2016 | 4.37% | 9,270.0M USD (NetCashProvidedByUsedInInvestingActivitiesContinuingOperations) | 9,675.0M USD (NetCashProvidedByUsedInInvestingActivities) | not reported |
| GS | investing_cash_flow | 2017 | 9.41% | -29,116.0M USD (NetCashProvidedByUsedInInvestingActivitiesContinuingOperations) | -26,377.0M USD (NetCashProvidedByUsedInInvestingActivities) | not reported |
| GS | operating_cash_flow | 2016 | 16.59% | 5,570.0M USD (NetCashProvidedByUsedInOperatingActivitiesContinuingOperations) | 6,494.0M USD (NetCashProvidedByUsedInOperatingActivities) | not reported |
| GS | operating_cash_flow | 2017 | 15.48% | -17,742.0M USD (NetCashProvidedByUsedInOperatingActivitiesContinuingOperations) | -20,489.0M USD (NetCashProvidedByUsedInOperatingActivities) | not reported |
| LMT | revenue | 2017 | 2.13% | 51,048.0M USD (SalesRevenueNet) | 49,960.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |
| MS | operating_cash_flow | 2016 | 119.98% | 2,447.0M USD (NetCashProvidedByUsedInOperatingActivitiesContinuingOperations) | 5,383.0M USD (NetCashProvidedByUsedInOperatingActivities) | not reported |
| MSFT | revenue | 2017 | 7.36% | 89,950.0M USD (SalesRevenueNet) | 96,571.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |
| ORCL | revenue | 2018 | 1.12% | 39,831.0M USD (Revenues) | 39,383.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |
| PFE | revenue | 2022 | 8.51% | 100,330.0M USD (Revenues) | 91,793.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | 100,330.0M USD |
| TGT | revenue | 2016 | 1.12% | 69,495.0M USD (SalesRevenueNet) | 70,271.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |
| TGT | revenue | 2017 | 1.16% | 71,879.0M USD (SalesRevenueNet) | 72,714.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |
| TSLA | investing_cash_flow | 2016 | 23.68% | -1,416.4M USD (NetCashProvidedByUsedInInvestingActivitiesContinuingOperations) | -1,081.1M USD (NetCashProvidedByUsedInInvestingActivities) | not reported |
| TSLA | investing_cash_flow | 2017 | 5.05% | -4,419.0M USD (NetCashProvidedByUsedInInvestingActivitiesContinuingOperations) | -4,196.0M USD (NetCashProvidedByUsedInInvestingActivities) | not reported |
| UPS | revenue | 2016 | 1.16% | 60,906.0M USD (Revenues) | 61,610.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |
| UPS | revenue | 2017 | 1.08% | 65,872.0M USD (Revenues) | 66,585.0M USD (RevenueFromContractWithCustomerExcludingAssessedTax) | not reported |

## The 25 largest relative gaps (all concepts, across-tag own)

| # | ticker | concept | FY | gap | own value | own tag | own accession (filed) | shown value | shown tag | shown accession (filed) | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TSLA | long_term_debt | 2016 | 99900.00% | 5.9M USD | LongTermDebt | 10-K 0001564590-17-003118 (2017-03-01) | 5,892.0M USD | LongTermDebt | 10-K 0001564590-18-002956 (2018-02-23) | no us-gaap tag in either filing carries the other's value; 6/156 shared same-year currency lines changed, net income unchanged; bucket: scale factor of 1000^n |
| 2 | GE | earnings_per_share | 2019 | 704.84% | -0.62 USD/shares | EarningsPerShareBasic | 10-K 0000040545-20-000009 (2020-02-24) | -4.99 USD/shares | EarningsPerShareBasic | 10-K 0000040545-22-000008 (2022-02-11) | split-like ratio x8; 40/96 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetCashProvidedByUsedInOperatingActivities; 5 discontinued-operations lines changed; bucket: per-share split |
| 3 | GE | eps_diluted | 2019 | 704.84% | -0.62 USD/shares | EarningsPerShareDiluted | 10-K 0000040545-20-000009 (2020-02-24) | -4.99 USD/shares | EarningsPerShareDiluted | 10-K 0000040545-22-000008 (2022-02-11) | split-like ratio x8; 40/96 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetCashProvidedByUsedInOperatingActivities; 5 discontinued-operations lines changed; bucket: per-share split |
| 4 | GE | earnings_per_share | 2020 | 700.00% | 0.58 USD/shares | EarningsPerShareBasic | 10-K 0000040545-21-000011 (2021-02-12) | 4.64 USD/shares | EarningsPerShareBasic | 8-K 0000040545-23-000137 (2023-04-25) | split-like ratio x8; 59/98 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetCashProvidedByUsedInOperatingActivities; 5 discontinued-operations lines changed; bucket: per-share split |
| 5 | GE | eps_diluted | 2020 | 700.00% | 0.58 USD/shares | EarningsPerShareDiluted | 10-K 0000040545-21-000011 (2021-02-12) | 4.64 USD/shares | EarningsPerShareDiluted | 8-K 0000040545-23-000137 (2023-04-25) | split-like ratio x8; 59/98 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetCashProvidedByUsedInOperatingActivities; 5 discontinued-operations lines changed; bucket: per-share split |
| 6 | GS | operating_cash_flow | 2021 | 583.82% | 921.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0001193125-22-052682 (2022-02-25) | 6,298.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000886982-24-000006 (2024-02-23) | no us-gaap tag in either filing carries the other's value; 5/80 shared same-year currency lines changed, net income unchanged; headline lines changed: NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged |
| 7 | GE | operating_cash_flow | 2016 | 575.41% | -244.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000040545-17-000010 (2017-02-24) | 1,160.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000040545-19-000014 (2019-02-26) | sign differs; no us-gaap tag in either filing carries the other's value; 58/98 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss, Assets, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; 2 discontinued-operations lines changed; bucket: discontinued-operations recast |
| 8 | JPM | investing_cash_flow | 2017 | 374.72% | -10,283.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000019617-18-000057 (2018-02-27) | 28,249.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000019617-20-000257 (2020-02-25) | sign differs; no us-gaap tag in either filing carries the other's value; 23/133 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged |
| 9 | BA | shareholders_equity | 2017 | 366.48% | 355.0M USD | StockholdersEquity | 10-K 0000012927-18-000007 (2018-02-12) | 1,656.0M USD | StockholdersEquity | 10-K 0000012927-19-000010 (2019-02-08) | no us-gaap tag in either filing carries the other's value; 64/222 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, CostOfRevenue, OperatingIncomeLoss, NetIncomeLoss, Assets, StockholdersEquity; bucket: broad recast, net income changed |
| 10 | JPM | operating_cash_flow | 2017 | 332.91% | -2,501.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000019617-18-000057 (2018-02-27) | -10,827.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000019617-20-000257 (2020-02-25) | no us-gaap tag in either filing carries the other's value; 23/133 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged |
| 11 | CRM | operating_income | 2017 | 239.42% | 64.2M USD | OperatingIncomeLoss | 10-K 0001108524-17-000006 (2017-03-06) | 218.0M USD | OperatingIncomeLoss | 10-K 0001108524-19-000009 (2019-03-08) | no us-gaap tag in either filing carries the other's value; 65/83 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed |
| 12 | AMD | financing_cash_flow | 2021 | 200.00% | -1,895.0M USD | NetCashProvidedByUsedInFinancingActivities | 10-K 0000002488-22-000016 (2022-02-03) | 1,895.0M USD | NetCashProvidedByUsedInFinancingActivities | 10-K 0000002488-24-000012 (2024-01-31) | sign differs; no us-gaap tag in either filing carries the other's value; 9/78 shared same-year currency lines changed, net income unchanged; bucket: exact sign flip |
| 13 | AMD | investing_cash_flow | 2021 | 200.00% | -686.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000002488-22-000016 (2022-02-03) | 686.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000002488-24-000012 (2024-01-31) | sign differs; no us-gaap tag in either filing carries the other's value; 9/78 shared same-year currency lines changed, net income unchanged; bucket: exact sign flip |
| 14 | GE | eps_diluted | 2022 | 200.00% | -0.05 USD/shares | EarningsPerShareDiluted | 10-K 0000040545-23-000023 (2023-02-10) | 0.05 USD/shares | EarningsPerShareDiluted | 10-K 0000040545-25-000015 (2025-02-03) | sign differs; no us-gaap tag in either filing carries the other's value; 76/111 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss; 4 discontinued-operations lines changed; bucket: exact sign flip |
| 15 | CRM | eps_diluted | 2018 | 188.24% | 0.17 USD/shares | EarningsPerShareDiluted | 10-K 0001108524-18-000011 (2018-03-09) | 0.49 USD/shares | EarningsPerShareDiluted | 10-K 0001108524-20-000014 (2020-03-05) | no us-gaap tag in either filing carries the other's value; 58/71 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed |
| 16 | T | current_assets | 2021 | 184.63% | 59,997.0M USD | AssetsCurrent | 10-K 0000732717-22-000015 (2022-02-16) | 170,768.0M USD | AssetsCurrent | 10-K 0000732717-23-000011 (2023-02-13) | the later value also appears in the own filing as LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities (not a tag of this concept: may be coincidence); 124/196 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, OperatingIncomeLoss; bucket: broad recast, net income unchanged |
| 17 | GE | earnings_per_share | 2022 | 183.33% | -0.06 USD/shares | EarningsPerShareBasic | 10-K 0000040545-23-000023 (2023-02-10) | 0.05 USD/shares | EarningsPerShareBasic | 10-K 0000040545-25-000015 (2025-02-03) | sign differs; no us-gaap tag in either filing carries the other's value; 76/111 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss; 4 discontinued-operations lines changed; bucket: discontinued-operations recast |
| 18 | CRM | net_income | 2018 | 182.40% | 127.5M USD | NetIncomeLoss | 10-K 0001108524-18-000011 (2018-03-09) | 360.0M USD | NetIncomeLoss | 10-K 0001108524-20-000014 (2020-03-05) | no us-gaap tag in either filing carries the other's value; 58/71 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed |
| 19 | CRM | earnings_per_share | 2018 | 177.78% | 0.18 USD/shares | EarningsPerShareBasic | 10-K 0001108524-18-000011 (2018-03-09) | 0.50 USD/shares | EarningsPerShareBasic | 10-K 0001108524-20-000014 (2020-03-05) | no us-gaap tag in either filing carries the other's value; 58/71 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed |
| 20 | AMD | net_income | 2017 | 176.74% | 43.0M USD | NetIncomeLoss | 10-K 0000002488-18-000042 (2018-02-27) | -33.0M USD | NetIncomeLoss | 10-K 0000002488-20-000008 (2020-02-04) | sign differs; the own value also appears in the later filing as IncreaseDecreaseInAccountsPayableRelatedParties (not a tag of this concept: may be coincidence); the later value also appears in the own filing as NetCashProvidedByUsedInFinancingActivities (not a tag of this concept: may be coincidence); 25/74 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income changed |
| 21 | AMD | earnings_per_share | 2017 | 175.00% | 0.04 USD/shares | EarningsPerShareBasic | 10-K 0000002488-18-000042 (2018-02-27) | -0.03 USD/shares | EarningsPerShareBasic | 10-K 0000002488-20-000008 (2020-02-04) | sign differs; no us-gaap tag in either filing carries the other's value; 25/74 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income changed |
| 22 | AMD | eps_diluted | 2017 | 175.00% | 0.04 USD/shares | EarningsPerShareDiluted | 10-K 0000002488-18-000042 (2018-02-27) | -0.03 USD/shares | EarningsPerShareDiluted | 10-K 0000002488-20-000008 (2020-02-04) | sign differs; no us-gaap tag in either filing carries the other's value; 25/74 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income changed |
| 23 | PLD | operating_income | 2017 | 153.42% | 771.1M USD | OperatingIncomeLoss | 10-K 0001564590-18-002228 (2018-02-15) | 1,954.0M USD | OperatingIncomeLoss | 10-K 0001564590-20-004096 (2020-02-11) | no us-gaap tag in either filing carries the other's value; 4/85 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged |
| 24 | CAT | operating_income | 2016 | 133.33% | 498.0M USD | OperatingIncomeLoss | 10-K 0000018230-17-000041 (2017-02-15) | 1,162.0M USD | OperatingIncomeLoss | 10-K 0000018230-19-000034 (2019-02-14) | no us-gaap tag in either filing carries the other's value; 14/121 shared same-year currency lines changed, net income absent; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged |
| 25 | GE | investing_cash_flow | 2017 | 131.65% | 2,322.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000040545-18-000014 (2018-02-23) | 5,379.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000040545-20-000009 (2020-02-24) | no us-gaap tag in either filing carries the other's value; 68/88 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; 6 discontinued-operations lines changed; bucket: discontinued-operations recast |

Detail:

1. **TSLA long_term_debt FY2016** (period end 2016-12-31), gap 99900.00%
   - own: 5.9M USD, LongTermDebt, 10-K 0001564590-17-003118 filed 2017-03-01
   - shown: 5,892.0M USD, LongTermDebt, 10-K 0001564590-18-002956 filed 2018-02-23 (FY2017 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 6/156 shared same-year currency lines changed, net income unchanged; bucket: scale factor of 1000^n
   - changed same-year currency lines: DebtCurrent, DebtInstrumentCarryingAmount, DebtInstrumentUnusedBorrowingCapacityAmount, LongTermDebt, NoncontrollingInterestIncreaseFromBusinessCombination, StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest
   - filings (10-Qs left out): 2017-03-01 10-K LongTermDebt 5.9M USD; 2018-02-23 10-K LongTermDebt 5,892.0M USD
2. **GE earnings_per_share FY2019** (period end 2019-12-31), gap 704.84%
   - own: -0.62 USD/shares, EarningsPerShareBasic, 10-K 0000040545-20-000009 filed 2020-02-24
   - shown: -4.99 USD/shares, EarningsPerShareBasic, 10-K 0000040545-22-000008 filed 2022-02-11 (FY2021 report)
   - evidence: split-like ratio x8; 40/96 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetCashProvidedByUsedInOperatingActivities; 5 discontinued-operations lines changed; bucket: per-share split
   - changed same-year currency lines: AmortizationOfIntangibleAssets, CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DepreciationAmortizationAndAccretionNet, GainLossOnDispositionOfAssets1, Goodwill, IncomeLossFromContinuingOperations, IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic, IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest +25 more
   - filings (10-Qs left out): 2020-02-24 10-K EarningsPerShareBasic -0.62 USD/shares; 2021-02-12 10-K EarningsPerShareBasic -0.62 USD/shares; 2022-02-11 10-K EarningsPerShareBasic -4.99 USD/shares
3. **GE eps_diluted FY2019** (period end 2019-12-31), gap 704.84%
   - own: -0.62 USD/shares, EarningsPerShareDiluted, 10-K 0000040545-20-000009 filed 2020-02-24
   - shown: -4.99 USD/shares, EarningsPerShareDiluted, 10-K 0000040545-22-000008 filed 2022-02-11 (FY2021 report)
   - evidence: split-like ratio x8; 40/96 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetCashProvidedByUsedInOperatingActivities; 5 discontinued-operations lines changed; bucket: per-share split
   - changed same-year currency lines: AmortizationOfIntangibleAssets, CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DepreciationAmortizationAndAccretionNet, GainLossOnDispositionOfAssets1, Goodwill, IncomeLossFromContinuingOperations, IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic, IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest +25 more
   - filings (10-Qs left out): 2020-02-24 10-K EarningsPerShareDiluted -0.62 USD/shares; 2021-02-12 10-K EarningsPerShareDiluted -0.62 USD/shares; 2022-02-11 10-K EarningsPerShareDiluted -4.99 USD/shares
4. **GE earnings_per_share FY2020** (period end 2020-12-31), gap 700.00%
   - own: 0.58 USD/shares, EarningsPerShareBasic, 10-K 0000040545-21-000011 filed 2021-02-12
   - shown: 4.64 USD/shares, EarningsPerShareBasic, 8-K 0000040545-23-000137 filed 2023-04-25
   - evidence: split-like ratio x8; 59/98 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetCashProvidedByUsedInOperatingActivities; 5 discontinued-operations lines changed; bucket: per-share split
   - changed same-year currency lines: AmortizationOfIntangibleAssets, CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DepreciationAmortizationAndAccretionNet, EnvironmentalRemediationExpense, EquitySecuritiesFvNiUnrealizedGainLoss, GainLossOnDispositionOfAssets1, Goodwill, GoodwillImpairmentLoss +44 more
   - filings (10-Qs left out): 2021-02-12 10-K EarningsPerShareBasic 0.58 USD/shares; 2022-02-11 10-K EarningsPerShareBasic 4.63 USD/shares; 2023-02-10 10-K EarningsPerShareBasic 4.63 USD/shares; 2023-04-25 8-K EarningsPerShareBasic 4.64 USD/shares
5. **GE eps_diluted FY2020** (period end 2020-12-31), gap 700.00%
   - own: 0.58 USD/shares, EarningsPerShareDiluted, 10-K 0000040545-21-000011 filed 2021-02-12
   - shown: 4.64 USD/shares, EarningsPerShareDiluted, 8-K 0000040545-23-000137 filed 2023-04-25
   - evidence: split-like ratio x8; 59/98 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetCashProvidedByUsedInOperatingActivities; 5 discontinued-operations lines changed; bucket: per-share split
   - changed same-year currency lines: AmortizationOfIntangibleAssets, CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DepreciationAmortizationAndAccretionNet, EnvironmentalRemediationExpense, EquitySecuritiesFvNiUnrealizedGainLoss, GainLossOnDispositionOfAssets1, Goodwill, GoodwillImpairmentLoss +44 more
   - filings (10-Qs left out): 2021-02-12 10-K EarningsPerShareDiluted 0.58 USD/shares; 2022-02-11 10-K EarningsPerShareDiluted 4.63 USD/shares; 2023-02-10 10-K EarningsPerShareDiluted 4.63 USD/shares; 2023-04-25 8-K EarningsPerShareDiluted 4.64 USD/shares
6. **GS operating_cash_flow FY2021** (period end 2021-12-31), gap 583.82%
   - own: 921.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0001193125-22-052682 filed 2022-02-25
   - shown: 6,298.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000886982-24-000006 filed 2024-02-23 (FY2023 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 5/80 shared same-year currency lines changed, net income unchanged; headline lines changed: NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged
   - changed same-year currency lines: BrokerageCommissionsRevenue, IncreaseDecreaseInOtherOperatingCapitalNet, InvestmentBankingRevenue, NetCashProvidedByUsedInOperatingActivities, UnrecognizedTaxBenefitsThatWouldImpactEffectiveTaxRate
   - filings (10-Qs left out): 2022-02-25 10-K NetCashProvidedByUsedInOperatingActivities 921.0M USD; 2023-02-24 10-K NetCashProvidedByUsedInOperatingActivities 6,298.0M USD; 2024-02-23 10-K NetCashProvidedByUsedInOperatingActivities 6,298.0M USD
7. **GE operating_cash_flow FY2016** (period end 2016-12-31), gap 575.41%
   - own: -244.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000040545-17-000010 filed 2017-02-24
   - shown: 1,160.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000040545-19-000014 filed 2019-02-26 (FY2018 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 58/98 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss, Assets, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; 2 discontinued-operations lines changed; bucket: discontinued-operations recast
   - changed same-year currency lines: Assets, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, ComprehensiveIncomeNetOfTax, ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostsAndExpenses, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DepreciationDepletionAndAmortization, IncomeLossAttributableToParent, IncomeLossFromContinuingOperations, IncomeLossFromContinuingOperationsAttributableToNoncontrollingEntity, IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic, IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest +43 more
   - filings (10-Qs left out): 2017-02-24 10-K NetCashProvidedByUsedInOperatingActivities -244.0M USD; 2017-02-24 10-K NetCashProvidedByUsedInOperatingActivitiesContinuingOperations 6,099.0M USD; 2018-02-23 10-K NetCashProvidedByUsedInOperatingActivities -244.0M USD; 2018-02-23 10-K NetCashProvidedByUsedInOperatingActivitiesContinuingOperations 6,099.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInOperatingActivities 1,160.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInOperatingActivitiesContinuingOperations 7,503.0M USD
8. **JPM investing_cash_flow FY2017** (period end 2017-12-31), gap 374.72%
   - own: -10,283.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000019617-18-000057 filed 2018-02-27
   - shown: 28,249.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000019617-20-000257 filed 2020-02-25 (FY2019 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 23/133 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CommunicationsAndInformationTechnology, FinancingReceivableIndividuallyEvaluatedForImpairment, GainLossOnSalesOfLoansNet, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets, InterestExpense, InterestExpenseTradingLiabilities, InterestIncomeDepositsWithFinancialInstitutions, InterestIncomeOperating, InterestIncomeOther, InterestIncomeSecuritiesTaxExempt, InvestmentBankingRevenue, LaborAndRelatedExpense, NetCashProvidedByUsedInInvestingActivities, NetCashProvidedByUsedInOperatingActivities, NoninterestExpense +8 more
   - filings (10-Qs left out): 2018-02-27 10-K NetCashProvidedByUsedInInvestingActivities -10,283.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInInvestingActivities 28,249.0M USD; 2020-02-25 10-K NetCashProvidedByUsedInInvestingActivities 28,249.0M USD
9. **BA shareholders_equity FY2017** (period end 2017-12-31), gap 366.48%
   - own: 355.0M USD, StockholdersEquity, 10-K 0000012927-18-000007 filed 2018-02-12
   - shown: 1,656.0M USD, StockholdersEquity, 10-K 0000012927-19-000010 filed 2019-02-08 (FY2018 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 64/222 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, CostOfRevenue, OperatingIncomeLoss, NetIncomeLoss, Assets, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AccountsReceivableNetCurrent, AccruedLiabilitiesCurrent, AccumulatedOtherComprehensiveIncomeLossNetOfTax, Assets, AssetsCurrent, AvailableForSaleSecurities, CashAndCashEquivalentsPeriodIncreaseDecrease, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostOfRevenue, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredIncomeTaxLiabilities, DeferredStateAndLocalIncomeTaxExpenseBenefit, DeferredTaxAssetsGross +49 more
   - filings (10-Qs left out): 2018-02-12 10-K StockholdersEquity 355.0M USD; 2018-02-12 10-K StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest 412.0M USD; 2019-02-08 10-K StockholdersEquity 1,656.0M USD; 2019-02-08 10-K StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest 1,713.0M USD; 2020-01-31 10-K StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest 1,713.0M USD; 2021-02-01 10-K StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest 1,713.0M USD
10. **JPM operating_cash_flow FY2017** (period end 2017-12-31), gap 332.91%
   - own: -2,501.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000019617-18-000057 filed 2018-02-27
   - shown: -10,827.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000019617-20-000257 filed 2020-02-25 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 23/133 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CommunicationsAndInformationTechnology, FinancingReceivableIndividuallyEvaluatedForImpairment, GainLossOnSalesOfLoansNet, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets, InterestExpense, InterestExpenseTradingLiabilities, InterestIncomeDepositsWithFinancialInstitutions, InterestIncomeOperating, InterestIncomeOther, InterestIncomeSecuritiesTaxExempt, InvestmentBankingRevenue, LaborAndRelatedExpense, NetCashProvidedByUsedInInvestingActivities, NetCashProvidedByUsedInOperatingActivities, NoninterestExpense +8 more
   - filings (10-Qs left out): 2018-02-27 10-K NetCashProvidedByUsedInOperatingActivities -2,501.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInOperatingActivities -10,827.0M USD; 2020-02-25 10-K NetCashProvidedByUsedInOperatingActivities -10,827.0M USD
11. **CRM operating_income FY2017** (period end 2017-01-31), gap 239.42%
   - own: 64.2M USD, OperatingIncomeLoss, 10-K 0001108524-17-000006 filed 2017-03-06
   - shown: 218.0M USD, OperatingIncomeLoss, 10-K 0001108524-19-000009 filed 2019-03-08 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 65/83 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AdvertisingExpense, AmortizationOfDebtDiscountPremium, AmortizationOfFinancingCosts, AmortizationOfFinancingCostsAndDiscounts, CashAndCashEquivalentsPeriodIncreaseDecrease, ComprehensiveIncomeNetOfTax, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, EffectOfExchangeRateOnCashAndCashEquivalents +50 more
   - filings (10-Qs left out): 2017-03-06 10-K OperatingIncomeLoss 64.2M USD; 2018-03-09 10-K OperatingIncomeLoss 64.2M USD; 2019-03-08 10-K OperatingIncomeLoss 218.0M USD
12. **AMD financing_cash_flow FY2021** (period end 2021-12-25), gap 200.00%
   - own: -1,895.0M USD, NetCashProvidedByUsedInFinancingActivities, 10-K 0000002488-22-000016 filed 2022-02-03
   - shown: 1,895.0M USD, NetCashProvidedByUsedInFinancingActivities, 10-K 0000002488-24-000012 filed 2024-01-31 (FY2023 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 9/78 shared same-year currency lines changed, net income unchanged; bucket: exact sign flip
   - changed same-year currency lines: DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, EffectiveIncomeTaxRateReconciliationShareBasedCompensationExcessTaxBenefitAmount, IncomeTaxReconciliationForeignIncomeTaxRateDifferential, IncomeTaxReconciliationOtherAdjustments, NetCashProvidedByUsedInFinancingActivities, NetCashProvidedByUsedInInvestingActivities, OtherNoncashIncomeExpense
   - filings (10-Qs left out): 2022-02-03 10-K NetCashProvidedByUsedInFinancingActivities -1,895.0M USD; 2023-02-27 10-K NetCashProvidedByUsedInFinancingActivities -1,895.0M USD; 2024-01-31 10-K NetCashProvidedByUsedInFinancingActivities 1,895.0M USD
13. **AMD investing_cash_flow FY2021** (period end 2021-12-25), gap 200.00%
   - own: -686.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000002488-22-000016 filed 2022-02-03
   - shown: 686.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000002488-24-000012 filed 2024-01-31 (FY2023 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 9/78 shared same-year currency lines changed, net income unchanged; bucket: exact sign flip
   - changed same-year currency lines: DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, EffectiveIncomeTaxRateReconciliationShareBasedCompensationExcessTaxBenefitAmount, IncomeTaxReconciliationForeignIncomeTaxRateDifferential, IncomeTaxReconciliationOtherAdjustments, NetCashProvidedByUsedInFinancingActivities, NetCashProvidedByUsedInInvestingActivities, OtherNoncashIncomeExpense
   - filings (10-Qs left out): 2022-02-03 10-K NetCashProvidedByUsedInInvestingActivities -686.0M USD; 2023-02-27 10-K NetCashProvidedByUsedInInvestingActivities -686.0M USD; 2024-01-31 10-K NetCashProvidedByUsedInInvestingActivities 686.0M USD
14. **GE eps_diluted FY2022** (period end 2022-12-31), gap 200.00%
   - own: -0.05 USD/shares, EarningsPerShareDiluted, 10-K 0000040545-23-000023 filed 2023-02-10
   - shown: 0.05 USD/shares, EarningsPerShareDiluted, 10-K 0000040545-25-000015 filed 2025-02-03 (FY2024 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 76/111 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss; 4 discontinued-operations lines changed; bucket: exact sign flip
   - changed same-year currency lines: AllocatedShareBasedCompensationExpense, AmortizationOfIntangibleAssets, CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations, ComprehensiveIncomeNetOfTax, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, DepreciationAmortizationAndAccretionNet +61 more
   - filings (10-Qs left out): 2023-02-10 10-K EarningsPerShareDiluted -0.05 USD/shares; 2023-04-25 8-K EarningsPerShareDiluted 0.05 USD/shares; 2024-02-02 10-K EarningsPerShareDiluted 0.05 USD/shares; 2025-02-03 10-K EarningsPerShareDiluted 0.05 USD/shares
15. **CRM eps_diluted FY2018** (period end 2018-01-31), gap 188.24%
   - own: 0.17 USD/shares, EarningsPerShareDiluted, 10-K 0001108524-18-000011 filed 2018-03-09
   - shown: 0.49 USD/shares, EarningsPerShareDiluted, 10-K 0001108524-20-000014 filed 2020-03-05 (FY2020 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 58/71 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AmortizationOfAboveAndBelowMarketLeases, AmortizationOfDebtDiscountPremium, AmortizationOfFinancingCosts, ComprehensiveIncomeNetOfTax, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredCompensationArrangementWithIndividualContributionsByEmployer, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, DeferredTaxAssetsLiabilitiesNet, DepreciationAndAmortization +43 more
   - filings (10-Qs left out): 2018-03-09 10-K EarningsPerShareDiluted 0.17 USD/shares; 2019-03-08 10-K EarningsPerShareDiluted 0.49 USD/shares; 2020-03-05 10-K EarningsPerShareDiluted 0.49 USD/shares
16. **T current_assets FY2021** (period end 2021-12-31), gap 184.63%
   - own: 59,997.0M USD, AssetsCurrent, 10-K 0000732717-22-000015 filed 2022-02-16
   - shown: 170,768.0M USD, AssetsCurrent, 10-K 0000732717-23-000011 filed 2023-02-13 (FY2022 report)
   - evidence: the later value also appears in the own filing as LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities (not a tag of this concept: may be coincidence); 124/196 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: AccountsPayableAndAccruedLiabilitiesCurrent, AccountsPayableCurrent, AccountsReceivableNetCurrent, AccruedIncomeTaxes, AccruedParticipationLiabilitiesDueInNextOperatingCycle, AdjustmentsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivities, AdvertisingExpense, AllocatedShareBasedCompensationExpense, AllowanceForDoubtfulAccountsReceivableCurrent, AssetsCurrent, AvailableForSaleSecuritiesDebtSecurities, CashAndCashEquivalentsAtCarryingValue, ContractWithCustomerAssetNet, ContractWithCustomerLiability, CostsAndExpenses +109 more
   - filings (10-Qs left out): 2022-02-16 10-K AssetsCurrent 59,997.0M USD; 2023-02-13 10-K AssetsCurrent 170,768.0M USD
17. **GE earnings_per_share FY2022** (period end 2022-12-31), gap 183.33%
   - own: -0.06 USD/shares, EarningsPerShareBasic, 10-K 0000040545-23-000023 filed 2023-02-10
   - shown: 0.05 USD/shares, EarningsPerShareBasic, 10-K 0000040545-25-000015 filed 2025-02-03 (FY2024 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 76/111 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss; 4 discontinued-operations lines changed; bucket: discontinued-operations recast
   - changed same-year currency lines: AllocatedShareBasedCompensationExpense, AmortizationOfIntangibleAssets, CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations, ComprehensiveIncomeNetOfTax, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, DepreciationAmortizationAndAccretionNet +61 more
   - filings (10-Qs left out): 2023-02-10 10-K EarningsPerShareBasic -0.06 USD/shares; 2023-04-25 8-K EarningsPerShareBasic 0.05 USD/shares; 2024-02-02 10-K EarningsPerShareBasic 0.05 USD/shares; 2025-02-03 10-K EarningsPerShareBasic 0.05 USD/shares
18. **CRM net_income FY2018** (period end 2018-01-31), gap 182.40%
   - own: 127.5M USD, NetIncomeLoss, 10-K 0001108524-18-000011 filed 2018-03-09
   - shown: 360.0M USD, NetIncomeLoss, 10-K 0001108524-20-000014 filed 2020-03-05 (FY2020 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 58/71 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AmortizationOfAboveAndBelowMarketLeases, AmortizationOfDebtDiscountPremium, AmortizationOfFinancingCosts, ComprehensiveIncomeNetOfTax, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredCompensationArrangementWithIndividualContributionsByEmployer, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, DeferredTaxAssetsLiabilitiesNet, DepreciationAndAmortization +43 more
   - filings (10-Qs left out): 2018-03-09 10-K NetIncomeLoss 127.5M USD; 2019-03-08 10-K NetIncomeLoss 360.0M USD; 2020-03-05 10-K NetIncomeLoss 360.0M USD
19. **CRM earnings_per_share FY2018** (period end 2018-01-31), gap 177.78%
   - own: 0.18 USD/shares, EarningsPerShareBasic, 10-K 0001108524-18-000011 filed 2018-03-09
   - shown: 0.50 USD/shares, EarningsPerShareBasic, 10-K 0001108524-20-000014 filed 2020-03-05 (FY2020 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 58/71 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AmortizationOfAboveAndBelowMarketLeases, AmortizationOfDebtDiscountPremium, AmortizationOfFinancingCosts, ComprehensiveIncomeNetOfTax, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredCompensationArrangementWithIndividualContributionsByEmployer, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, DeferredTaxAssetsLiabilitiesNet, DepreciationAndAmortization +43 more
   - filings (10-Qs left out): 2018-03-09 10-K EarningsPerShareBasic 0.18 USD/shares; 2019-03-08 10-K EarningsPerShareBasic 0.50 USD/shares; 2020-03-05 10-K EarningsPerShareBasic 0.50 USD/shares
20. **AMD net_income FY2017** (period end 2017-12-30), gap 176.74%
   - own: 43.0M USD, NetIncomeLoss, 10-K 0000002488-18-000042 filed 2018-02-27
   - shown: -33.0M USD, NetIncomeLoss, 10-K 0000002488-20-000008 filed 2020-02-04 (FY2019 report)
   - evidence: sign differs; the own value also appears in the later filing as IncreaseDecreaseInAccountsPayableRelatedParties (not a tag of this concept: may be coincidence); the later value also appears in the own filing as NetCashProvidedByUsedInFinancingActivities (not a tag of this concept: may be coincidence); 25/74 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income changed
   - changed same-year currency lines: ComprehensiveIncomeNetOfTax, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, GrossProfit, IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic, IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest, IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign, IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments, IncomeTaxExpenseBenefit, IncomeTaxReconciliationChangeInDeferredTaxAssetsValuationAllowance, IncreaseDecreaseInAccountsPayableAndAccruedLiabilities, IncreaseDecreaseInAccountsPayableRelatedParties, IncreaseDecreaseInAccountsReceivable, IncreaseDecreaseInInventories, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets +10 more
   - filings (10-Qs left out): 2018-02-27 10-K NetIncomeLoss 43.0M USD; 2019-02-08 10-K NetIncomeLoss -33.0M USD; 2020-02-04 10-K NetIncomeLoss -33.0M USD
21. **AMD earnings_per_share FY2017** (period end 2017-12-30), gap 175.00%
   - own: 0.04 USD/shares, EarningsPerShareBasic, 10-K 0000002488-18-000042 filed 2018-02-27
   - shown: -0.03 USD/shares, EarningsPerShareBasic, 10-K 0000002488-20-000008 filed 2020-02-04 (FY2019 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 25/74 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income changed
   - changed same-year currency lines: ComprehensiveIncomeNetOfTax, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, GrossProfit, IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic, IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest, IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign, IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments, IncomeTaxExpenseBenefit, IncomeTaxReconciliationChangeInDeferredTaxAssetsValuationAllowance, IncreaseDecreaseInAccountsPayableAndAccruedLiabilities, IncreaseDecreaseInAccountsPayableRelatedParties, IncreaseDecreaseInAccountsReceivable, IncreaseDecreaseInInventories, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets +10 more
   - filings (10-Qs left out): 2018-02-27 10-K EarningsPerShareBasic 0.04 USD/shares; 2019-02-08 10-K EarningsPerShareBasic -0.03 USD/shares; 2020-02-04 10-K EarningsPerShareBasic -0.03 USD/shares
22. **AMD eps_diluted FY2017** (period end 2017-12-30), gap 175.00%
   - own: 0.04 USD/shares, EarningsPerShareDiluted, 10-K 0000002488-18-000042 filed 2018-02-27
   - shown: -0.03 USD/shares, EarningsPerShareDiluted, 10-K 0000002488-20-000008 filed 2020-02-04 (FY2019 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 25/74 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income changed
   - changed same-year currency lines: ComprehensiveIncomeNetOfTax, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, GrossProfit, IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic, IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest, IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign, IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments, IncomeTaxExpenseBenefit, IncomeTaxReconciliationChangeInDeferredTaxAssetsValuationAllowance, IncreaseDecreaseInAccountsPayableAndAccruedLiabilities, IncreaseDecreaseInAccountsPayableRelatedParties, IncreaseDecreaseInAccountsReceivable, IncreaseDecreaseInInventories, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets +10 more
   - filings (10-Qs left out): 2018-02-27 10-K EarningsPerShareDiluted 0.04 USD/shares; 2019-02-08 10-K EarningsPerShareDiluted -0.03 USD/shares; 2020-02-04 10-K EarningsPerShareDiluted -0.03 USD/shares
23. **PLD operating_income FY2017** (period end 2017-12-31), gap 153.42%
   - own: 771.1M USD, OperatingIncomeLoss, 10-K 0001564590-18-002228 filed 2018-02-15
   - shown: 1,954.0M USD, OperatingIncomeLoss, 10-K 0001564590-20-004096 filed 2020-02-11 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 4/85 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: GainLossOnFairValueHedgesRecognizedInEarnings, NonoperatingIncomeExpense, OperatingIncomeLoss, OperatingLeasesIncomeStatementLeaseRevenue
   - filings (10-Qs left out): 2018-02-15 10-K OperatingIncomeLoss 771.1M USD; 2019-02-13 10-K OperatingIncomeLoss 771.1M USD; 2020-02-11 10-K OperatingIncomeLoss 1,954.0M USD
24. **CAT operating_income FY2016** (period end 2016-12-31), gap 133.33%
   - own: 498.0M USD, OperatingIncomeLoss, 10-K 0000018230-17-000041 filed 2017-02-15
   - shown: 1,162.0M USD, OperatingIncomeLoss, 10-K 0000018230-19-000034 filed 2019-02-14 (FY2018 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 14/121 shared same-year currency lines changed, net income absent; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CashAndCashEquivalentsPeriodIncreaseDecrease, IncreaseDecreaseInCustomerAdvances, IncreaseDecreaseInOtherOperatingLiabilities, NetCashProvidedByUsedInFinancingActivitiesContinuingOperations, NetCashProvidedByUsedInInvestingActivitiesContinuingOperations, NetCashProvidedByUsedInOperatingActivitiesContinuingOperations, OperatingExpenses, OperatingIncomeLoss, OtherNoncashIncomeExpense, OtherNonoperatingIncomeExpense, OtherOperatingIncomeExpenseNet, PaymentsForProceedsFromOtherInvestingActivities, ResearchAndDevelopmentExpense, SellingGeneralAndAdministrativeExpense
   - filings (10-Qs left out): 2017-02-15 10-K OperatingIncomeLoss 498.0M USD; 2018-02-15 10-K OperatingIncomeLoss 498.0M USD; 2019-02-14 10-K OperatingIncomeLoss 1,162.0M USD
25. **GE investing_cash_flow FY2017** (period end 2017-12-31), gap 131.65%
   - own: 2,322.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000040545-18-000014 filed 2018-02-23
   - shown: 5,379.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000040545-20-000009 filed 2020-02-24 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 68/88 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; 6 discontinued-operations lines changed; bucket: discontinued-operations recast
   - changed same-year currency lines: CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations, ComprehensiveIncomeNetOfTax, ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, Depreciation, DepreciationAmortizationAndAccretionNet +53 more
   - filings (10-Qs left out): 2018-02-23 10-K NetCashProvidedByUsedInInvestingActivities 2,322.0M USD; 2018-02-23 10-K NetCashProvidedByUsedInInvestingActivitiesContinuingOperations 3,940.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInInvestingActivities 6,564.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInInvestingActivitiesContinuingOperations 8,348.0M USD; 2020-02-24 10-K NetCashProvidedByUsedInInvestingActivities 5,379.0M USD; 2020-02-24 10-K NetCashProvidedByUsedInInvestingActivitiesContinuingOperations 6,728.0M USD

## The 25 largest relative gaps (amounts only, per-share excluded, at most two per company, across-tag own)

| # | ticker | concept | FY | gap | own value | own tag | own accession (filed) | shown value | shown tag | shown accession (filed) | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TSLA | long_term_debt | 2016 | 99900.00% | 5.9M USD | LongTermDebt | 10-K 0001564590-17-003118 (2017-03-01) | 5,892.0M USD | LongTermDebt | 10-K 0001564590-18-002956 (2018-02-23) | no us-gaap tag in either filing carries the other's value; 6/156 shared same-year currency lines changed, net income unchanged; bucket: scale factor of 1000^n |
| 2 | GS | operating_cash_flow | 2021 | 583.82% | 921.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0001193125-22-052682 (2022-02-25) | 6,298.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000886982-24-000006 (2024-02-23) | no us-gaap tag in either filing carries the other's value; 5/80 shared same-year currency lines changed, net income unchanged; headline lines changed: NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged |
| 3 | GE | operating_cash_flow | 2016 | 575.41% | -244.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000040545-17-000010 (2017-02-24) | 1,160.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000040545-19-000014 (2019-02-26) | sign differs; no us-gaap tag in either filing carries the other's value; 58/98 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss, Assets, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; 2 discontinued-operations lines changed; bucket: discontinued-operations recast |
| 4 | JPM | investing_cash_flow | 2017 | 374.72% | -10,283.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000019617-18-000057 (2018-02-27) | 28,249.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000019617-20-000257 (2020-02-25) | sign differs; no us-gaap tag in either filing carries the other's value; 23/133 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged |
| 5 | BA | shareholders_equity | 2017 | 366.48% | 355.0M USD | StockholdersEquity | 10-K 0000012927-18-000007 (2018-02-12) | 1,656.0M USD | StockholdersEquity | 10-K 0000012927-19-000010 (2019-02-08) | no us-gaap tag in either filing carries the other's value; 64/222 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, CostOfRevenue, OperatingIncomeLoss, NetIncomeLoss, Assets, StockholdersEquity; bucket: broad recast, net income changed |
| 6 | JPM | operating_cash_flow | 2017 | 332.91% | -2,501.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000019617-18-000057 (2018-02-27) | -10,827.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000019617-20-000257 (2020-02-25) | no us-gaap tag in either filing carries the other's value; 23/133 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged |
| 7 | CRM | operating_income | 2017 | 239.42% | 64.2M USD | OperatingIncomeLoss | 10-K 0001108524-17-000006 (2017-03-06) | 218.0M USD | OperatingIncomeLoss | 10-K 0001108524-19-000009 (2019-03-08) | no us-gaap tag in either filing carries the other's value; 65/83 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed |
| 8 | AMD | financing_cash_flow | 2021 | 200.00% | -1,895.0M USD | NetCashProvidedByUsedInFinancingActivities | 10-K 0000002488-22-000016 (2022-02-03) | 1,895.0M USD | NetCashProvidedByUsedInFinancingActivities | 10-K 0000002488-24-000012 (2024-01-31) | sign differs; no us-gaap tag in either filing carries the other's value; 9/78 shared same-year currency lines changed, net income unchanged; bucket: exact sign flip |
| 9 | AMD | investing_cash_flow | 2021 | 200.00% | -686.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000002488-22-000016 (2022-02-03) | 686.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000002488-24-000012 (2024-01-31) | sign differs; no us-gaap tag in either filing carries the other's value; 9/78 shared same-year currency lines changed, net income unchanged; bucket: exact sign flip |
| 10 | T | current_assets | 2021 | 184.63% | 59,997.0M USD | AssetsCurrent | 10-K 0000732717-22-000015 (2022-02-16) | 170,768.0M USD | AssetsCurrent | 10-K 0000732717-23-000011 (2023-02-13) | the later value also appears in the own filing as LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities (not a tag of this concept: may be coincidence); 124/196 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, OperatingIncomeLoss; bucket: broad recast, net income unchanged |
| 11 | CRM | net_income | 2018 | 182.40% | 127.5M USD | NetIncomeLoss | 10-K 0001108524-18-000011 (2018-03-09) | 360.0M USD | NetIncomeLoss | 10-K 0001108524-20-000014 (2020-03-05) | no us-gaap tag in either filing carries the other's value; 58/71 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed |
| 12 | PLD | operating_income | 2017 | 153.42% | 771.1M USD | OperatingIncomeLoss | 10-K 0001564590-18-002228 (2018-02-15) | 1,954.0M USD | OperatingIncomeLoss | 10-K 0001564590-20-004096 (2020-02-11) | no us-gaap tag in either filing carries the other's value; 4/85 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged |
| 13 | CAT | operating_income | 2016 | 133.33% | 498.0M USD | OperatingIncomeLoss | 10-K 0000018230-17-000041 (2017-02-15) | 1,162.0M USD | OperatingIncomeLoss | 10-K 0000018230-19-000034 (2019-02-14) | no us-gaap tag in either filing carries the other's value; 14/121 shared same-year currency lines changed, net income absent; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged |
| 14 | GE | investing_cash_flow | 2017 | 131.65% | 2,322.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000040545-18-000014 (2018-02-23) | 5,379.0M USD | NetCashProvidedByUsedInInvestingActivities | 10-K 0000040545-20-000009 (2020-02-24) | no us-gaap tag in either filing carries the other's value; 68/88 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; 6 discontinued-operations lines changed; bucket: discontinued-operations recast |
| 15 | MS | operating_cash_flow | 2016 | 119.98% | 2,447.0M USD | NetCashProvidedByUsedInOperatingActivitiesContinuingOperations | 10-K 0001193125-17-059212 (2017-02-27) | 5,383.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0001193125-19-051943 (2019-02-26) | tag changed NetCashProvidedByUsedInOperatingActivitiesContinuingOperations -> NetCashProvidedByUsedInOperatingActivities; no us-gaap tag in either filing carries the other's value; 9/118 shared same-year currency lines changed, net income unchanged; bucket: own value under another tag of the concept |
| 16 | CVS | net_interest_income | 2016 | 100.00% | -1,058.0M USD | InterestIncomeExpenseNet | 10-K 0000064803-17-000006 (2017-02-09) | 0 USD | InterestIncomeExpenseNet | 8-K 0000064803-19-000042 (2019-08-08) | no us-gaap tag in either filing carries the other's value; 9/70 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged |
| 17 | CVS | net_interest_income | 2017 | 100.00% | -1,041.0M USD | InterestIncomeExpenseNet | 10-K 0001558370-18-000707 (2018-02-14) | 0 USD | InterestIncomeExpenseNet | 10-K 0000064803-20-000007 (2020-02-18) | no us-gaap tag in either filing carries the other's value; 8/74 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged |
| 18 | FDX | net_income | 2026 | 100.00% | 4,433.0M USD | NetIncomeLoss | 10-K 0001048911-26-000105 (2026-07-20) | 4,433 USD | NetIncomeLoss | DEF 14A 0001104659-26-097836 (2026-08-17) | no us-gaap tag in either filing carries the other's value; 1/1 shared same-year currency lines changed, net income changed; headline lines changed: NetIncomeLoss; bucket: shown value from a proxy statement |
| 19 | FDX | net_income | 2024 | 100.00% | 4,331.0M USD | NetIncomeLoss | 10-K 0000950170-24-083577 (2024-07-15) | 4,331 USD | NetIncomeLoss | DEF 14A 0001104659-26-097836 (2026-08-17) | no us-gaap tag in either filing carries the other's value; 1/1 shared same-year currency lines changed, net income changed; headline lines changed: NetIncomeLoss; bucket: shown value from a proxy statement |
| 20 | PLD | operating_income | 2018 | 99.29% | 847.0M USD | OperatingIncomeLoss | 10-K 0001564590-19-002872 (2019-02-13) | 1,688.0M USD | OperatingIncomeLoss | 10-K 0001564590-21-005312 (2021-02-11) | no us-gaap tag in either filing carries the other's value; 4/88 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged |
| 21 | MS | cash_and_equivalents | 2016 | 78.33% | 43,381.0M USD | CashAndCashEquivalentsAtCarryingValue | 10-K 0001193125-17-059212 (2017-02-27) | 77,360.0M USD | CashAndCashEquivalentsAtCarryingValue | 10-K 0001193125-19-051943 (2019-02-26) | no us-gaap tag in either filing carries the other's value; 9/118 shared same-year currency lines changed, net income unchanged; bucket: broad recast, net income unchanged |
| 22 | UPS | operating_income | 2016 | 40.63% | 5,467.0M USD | OperatingIncomeLoss | 10-K 0001090727-17-000011 (2017-02-21) | 7,688.0M USD | OperatingIncomeLoss | 10-K 0001090727-19-000006 (2019-02-21) | no us-gaap tag in either filing carries the other's value; 22/75 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, Assets; bucket: broad recast, net income changed |
| 23 | GS | operating_cash_flow | 2020 | 35.02% | -13,728.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0001193125-21-049380 (2021-02-22) | -18,535.0M USD | NetCashProvidedByUsedInOperatingActivities | 10-K 0000886982-23-000003 (2023-02-24) | no us-gaap tag in either filing carries the other's value; 4/82 shared same-year currency lines changed, net income unchanged; headline lines changed: NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged |
| 24 | BA | current_liabilities | 2017 | 32.66% | 56,269.0M USD | LiabilitiesCurrent | 10-K 0000012927-18-000007 (2018-02-12) | 74,648.0M USD | LiabilitiesCurrent | 10-K 0000012927-19-000010 (2019-02-08) | no us-gaap tag in either filing carries the other's value; 64/222 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, CostOfRevenue, OperatingIncomeLoss, NetIncomeLoss, Assets, StockholdersEquity; bucket: broad recast, net income changed |
| 25 | T | operating_income | 2020 | 30.71% | 6,405.0M USD | OperatingIncomeLoss | 10-K 0000732717-21-000012 (2021-02-25) | 8,372.0M USD | OperatingIncomeLoss | 10-K 0000732717-23-000011 (2023-02-13) | no us-gaap tag in either filing carries the other's value; 63/115 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, OperatingIncomeLoss; bucket: broad recast, net income unchanged |

Detail:

1. **TSLA long_term_debt FY2016** (period end 2016-12-31), gap 99900.00%
   - own: 5.9M USD, LongTermDebt, 10-K 0001564590-17-003118 filed 2017-03-01
   - shown: 5,892.0M USD, LongTermDebt, 10-K 0001564590-18-002956 filed 2018-02-23 (FY2017 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 6/156 shared same-year currency lines changed, net income unchanged; bucket: scale factor of 1000^n
   - changed same-year currency lines: DebtCurrent, DebtInstrumentCarryingAmount, DebtInstrumentUnusedBorrowingCapacityAmount, LongTermDebt, NoncontrollingInterestIncreaseFromBusinessCombination, StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest
   - filings (10-Qs left out): 2017-03-01 10-K LongTermDebt 5.9M USD; 2018-02-23 10-K LongTermDebt 5,892.0M USD
2. **GS operating_cash_flow FY2021** (period end 2021-12-31), gap 583.82%
   - own: 921.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0001193125-22-052682 filed 2022-02-25
   - shown: 6,298.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000886982-24-000006 filed 2024-02-23 (FY2023 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 5/80 shared same-year currency lines changed, net income unchanged; headline lines changed: NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged
   - changed same-year currency lines: BrokerageCommissionsRevenue, IncreaseDecreaseInOtherOperatingCapitalNet, InvestmentBankingRevenue, NetCashProvidedByUsedInOperatingActivities, UnrecognizedTaxBenefitsThatWouldImpactEffectiveTaxRate
   - filings (10-Qs left out): 2022-02-25 10-K NetCashProvidedByUsedInOperatingActivities 921.0M USD; 2023-02-24 10-K NetCashProvidedByUsedInOperatingActivities 6,298.0M USD; 2024-02-23 10-K NetCashProvidedByUsedInOperatingActivities 6,298.0M USD
3. **GE operating_cash_flow FY2016** (period end 2016-12-31), gap 575.41%
   - own: -244.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000040545-17-000010 filed 2017-02-24
   - shown: 1,160.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000040545-19-000014 filed 2019-02-26 (FY2018 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 58/98 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss, Assets, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; 2 discontinued-operations lines changed; bucket: discontinued-operations recast
   - changed same-year currency lines: Assets, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, ComprehensiveIncomeNetOfTax, ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostsAndExpenses, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DepreciationDepletionAndAmortization, IncomeLossAttributableToParent, IncomeLossFromContinuingOperations, IncomeLossFromContinuingOperationsAttributableToNoncontrollingEntity, IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic, IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest +43 more
   - filings (10-Qs left out): 2017-02-24 10-K NetCashProvidedByUsedInOperatingActivities -244.0M USD; 2017-02-24 10-K NetCashProvidedByUsedInOperatingActivitiesContinuingOperations 6,099.0M USD; 2018-02-23 10-K NetCashProvidedByUsedInOperatingActivities -244.0M USD; 2018-02-23 10-K NetCashProvidedByUsedInOperatingActivitiesContinuingOperations 6,099.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInOperatingActivities 1,160.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInOperatingActivitiesContinuingOperations 7,503.0M USD
4. **JPM investing_cash_flow FY2017** (period end 2017-12-31), gap 374.72%
   - own: -10,283.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000019617-18-000057 filed 2018-02-27
   - shown: 28,249.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000019617-20-000257 filed 2020-02-25 (FY2019 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 23/133 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CommunicationsAndInformationTechnology, FinancingReceivableIndividuallyEvaluatedForImpairment, GainLossOnSalesOfLoansNet, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets, InterestExpense, InterestExpenseTradingLiabilities, InterestIncomeDepositsWithFinancialInstitutions, InterestIncomeOperating, InterestIncomeOther, InterestIncomeSecuritiesTaxExempt, InvestmentBankingRevenue, LaborAndRelatedExpense, NetCashProvidedByUsedInInvestingActivities, NetCashProvidedByUsedInOperatingActivities, NoninterestExpense +8 more
   - filings (10-Qs left out): 2018-02-27 10-K NetCashProvidedByUsedInInvestingActivities -10,283.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInInvestingActivities 28,249.0M USD; 2020-02-25 10-K NetCashProvidedByUsedInInvestingActivities 28,249.0M USD
5. **BA shareholders_equity FY2017** (period end 2017-12-31), gap 366.48%
   - own: 355.0M USD, StockholdersEquity, 10-K 0000012927-18-000007 filed 2018-02-12
   - shown: 1,656.0M USD, StockholdersEquity, 10-K 0000012927-19-000010 filed 2019-02-08 (FY2018 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 64/222 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, CostOfRevenue, OperatingIncomeLoss, NetIncomeLoss, Assets, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AccountsReceivableNetCurrent, AccruedLiabilitiesCurrent, AccumulatedOtherComprehensiveIncomeLossNetOfTax, Assets, AssetsCurrent, AvailableForSaleSecurities, CashAndCashEquivalentsPeriodIncreaseDecrease, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostOfRevenue, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredIncomeTaxLiabilities, DeferredStateAndLocalIncomeTaxExpenseBenefit, DeferredTaxAssetsGross +49 more
   - filings (10-Qs left out): 2018-02-12 10-K StockholdersEquity 355.0M USD; 2018-02-12 10-K StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest 412.0M USD; 2019-02-08 10-K StockholdersEquity 1,656.0M USD; 2019-02-08 10-K StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest 1,713.0M USD; 2020-01-31 10-K StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest 1,713.0M USD; 2021-02-01 10-K StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest 1,713.0M USD
6. **JPM operating_cash_flow FY2017** (period end 2017-12-31), gap 332.91%
   - own: -2,501.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000019617-18-000057 filed 2018-02-27
   - shown: -10,827.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000019617-20-000257 filed 2020-02-25 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 23/133 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CommunicationsAndInformationTechnology, FinancingReceivableIndividuallyEvaluatedForImpairment, GainLossOnSalesOfLoansNet, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets, InterestExpense, InterestExpenseTradingLiabilities, InterestIncomeDepositsWithFinancialInstitutions, InterestIncomeOperating, InterestIncomeOther, InterestIncomeSecuritiesTaxExempt, InvestmentBankingRevenue, LaborAndRelatedExpense, NetCashProvidedByUsedInInvestingActivities, NetCashProvidedByUsedInOperatingActivities, NoninterestExpense +8 more
   - filings (10-Qs left out): 2018-02-27 10-K NetCashProvidedByUsedInOperatingActivities -2,501.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInOperatingActivities -10,827.0M USD; 2020-02-25 10-K NetCashProvidedByUsedInOperatingActivities -10,827.0M USD
7. **CRM operating_income FY2017** (period end 2017-01-31), gap 239.42%
   - own: 64.2M USD, OperatingIncomeLoss, 10-K 0001108524-17-000006 filed 2017-03-06
   - shown: 218.0M USD, OperatingIncomeLoss, 10-K 0001108524-19-000009 filed 2019-03-08 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 65/83 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AdvertisingExpense, AmortizationOfDebtDiscountPremium, AmortizationOfFinancingCosts, AmortizationOfFinancingCostsAndDiscounts, CashAndCashEquivalentsPeriodIncreaseDecrease, ComprehensiveIncomeNetOfTax, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, EffectOfExchangeRateOnCashAndCashEquivalents +50 more
   - filings (10-Qs left out): 2017-03-06 10-K OperatingIncomeLoss 64.2M USD; 2018-03-09 10-K OperatingIncomeLoss 64.2M USD; 2019-03-08 10-K OperatingIncomeLoss 218.0M USD
8. **AMD financing_cash_flow FY2021** (period end 2021-12-25), gap 200.00%
   - own: -1,895.0M USD, NetCashProvidedByUsedInFinancingActivities, 10-K 0000002488-22-000016 filed 2022-02-03
   - shown: 1,895.0M USD, NetCashProvidedByUsedInFinancingActivities, 10-K 0000002488-24-000012 filed 2024-01-31 (FY2023 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 9/78 shared same-year currency lines changed, net income unchanged; bucket: exact sign flip
   - changed same-year currency lines: DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, EffectiveIncomeTaxRateReconciliationShareBasedCompensationExcessTaxBenefitAmount, IncomeTaxReconciliationForeignIncomeTaxRateDifferential, IncomeTaxReconciliationOtherAdjustments, NetCashProvidedByUsedInFinancingActivities, NetCashProvidedByUsedInInvestingActivities, OtherNoncashIncomeExpense
   - filings (10-Qs left out): 2022-02-03 10-K NetCashProvidedByUsedInFinancingActivities -1,895.0M USD; 2023-02-27 10-K NetCashProvidedByUsedInFinancingActivities -1,895.0M USD; 2024-01-31 10-K NetCashProvidedByUsedInFinancingActivities 1,895.0M USD
9. **AMD investing_cash_flow FY2021** (period end 2021-12-25), gap 200.00%
   - own: -686.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000002488-22-000016 filed 2022-02-03
   - shown: 686.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000002488-24-000012 filed 2024-01-31 (FY2023 report)
   - evidence: sign differs; no us-gaap tag in either filing carries the other's value; 9/78 shared same-year currency lines changed, net income unchanged; bucket: exact sign flip
   - changed same-year currency lines: DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, EffectiveIncomeTaxRateReconciliationShareBasedCompensationExcessTaxBenefitAmount, IncomeTaxReconciliationForeignIncomeTaxRateDifferential, IncomeTaxReconciliationOtherAdjustments, NetCashProvidedByUsedInFinancingActivities, NetCashProvidedByUsedInInvestingActivities, OtherNoncashIncomeExpense
   - filings (10-Qs left out): 2022-02-03 10-K NetCashProvidedByUsedInInvestingActivities -686.0M USD; 2023-02-27 10-K NetCashProvidedByUsedInInvestingActivities -686.0M USD; 2024-01-31 10-K NetCashProvidedByUsedInInvestingActivities 686.0M USD
10. **T current_assets FY2021** (period end 2021-12-31), gap 184.63%
   - own: 59,997.0M USD, AssetsCurrent, 10-K 0000732717-22-000015 filed 2022-02-16
   - shown: 170,768.0M USD, AssetsCurrent, 10-K 0000732717-23-000011 filed 2023-02-13 (FY2022 report)
   - evidence: the later value also appears in the own filing as LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities (not a tag of this concept: may be coincidence); 124/196 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: AccountsPayableAndAccruedLiabilitiesCurrent, AccountsPayableCurrent, AccountsReceivableNetCurrent, AccruedIncomeTaxes, AccruedParticipationLiabilitiesDueInNextOperatingCycle, AdjustmentsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivities, AdvertisingExpense, AllocatedShareBasedCompensationExpense, AllowanceForDoubtfulAccountsReceivableCurrent, AssetsCurrent, AvailableForSaleSecuritiesDebtSecurities, CashAndCashEquivalentsAtCarryingValue, ContractWithCustomerAssetNet, ContractWithCustomerLiability, CostsAndExpenses +109 more
   - filings (10-Qs left out): 2022-02-16 10-K AssetsCurrent 59,997.0M USD; 2023-02-13 10-K AssetsCurrent 170,768.0M USD
11. **CRM net_income FY2018** (period end 2018-01-31), gap 182.40%
   - own: 127.5M USD, NetIncomeLoss, 10-K 0001108524-18-000011 filed 2018-03-09
   - shown: 360.0M USD, NetIncomeLoss, 10-K 0001108524-20-000014 filed 2020-03-05 (FY2020 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 58/71 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AmortizationOfAboveAndBelowMarketLeases, AmortizationOfDebtDiscountPremium, AmortizationOfFinancingCosts, ComprehensiveIncomeNetOfTax, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredCompensationArrangementWithIndividualContributionsByEmployer, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, DeferredTaxAssetsLiabilitiesNet, DepreciationAndAmortization +43 more
   - filings (10-Qs left out): 2018-03-09 10-K NetIncomeLoss 127.5M USD; 2019-03-08 10-K NetIncomeLoss 360.0M USD; 2020-03-05 10-K NetIncomeLoss 360.0M USD
12. **PLD operating_income FY2017** (period end 2017-12-31), gap 153.42%
   - own: 771.1M USD, OperatingIncomeLoss, 10-K 0001564590-18-002228 filed 2018-02-15
   - shown: 1,954.0M USD, OperatingIncomeLoss, 10-K 0001564590-20-004096 filed 2020-02-11 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 4/85 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: GainLossOnFairValueHedgesRecognizedInEarnings, NonoperatingIncomeExpense, OperatingIncomeLoss, OperatingLeasesIncomeStatementLeaseRevenue
   - filings (10-Qs left out): 2018-02-15 10-K OperatingIncomeLoss 771.1M USD; 2019-02-13 10-K OperatingIncomeLoss 771.1M USD; 2020-02-11 10-K OperatingIncomeLoss 1,954.0M USD
13. **CAT operating_income FY2016** (period end 2016-12-31), gap 133.33%
   - own: 498.0M USD, OperatingIncomeLoss, 10-K 0000018230-17-000041 filed 2017-02-15
   - shown: 1,162.0M USD, OperatingIncomeLoss, 10-K 0000018230-19-000034 filed 2019-02-14 (FY2018 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 14/121 shared same-year currency lines changed, net income absent; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CashAndCashEquivalentsPeriodIncreaseDecrease, IncreaseDecreaseInCustomerAdvances, IncreaseDecreaseInOtherOperatingLiabilities, NetCashProvidedByUsedInFinancingActivitiesContinuingOperations, NetCashProvidedByUsedInInvestingActivitiesContinuingOperations, NetCashProvidedByUsedInOperatingActivitiesContinuingOperations, OperatingExpenses, OperatingIncomeLoss, OtherNoncashIncomeExpense, OtherNonoperatingIncomeExpense, OtherOperatingIncomeExpenseNet, PaymentsForProceedsFromOtherInvestingActivities, ResearchAndDevelopmentExpense, SellingGeneralAndAdministrativeExpense
   - filings (10-Qs left out): 2017-02-15 10-K OperatingIncomeLoss 498.0M USD; 2018-02-15 10-K OperatingIncomeLoss 498.0M USD; 2019-02-14 10-K OperatingIncomeLoss 1,162.0M USD
14. **GE investing_cash_flow FY2017** (period end 2017-12-31), gap 131.65%
   - own: 2,322.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000040545-18-000014 filed 2018-02-23
   - shown: 5,379.0M USD, NetCashProvidedByUsedInInvestingActivities, 10-K 0000040545-20-000009 filed 2020-02-24 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 68/88 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, IncomeLossFromContinuingOperations, NetIncomeLoss, StockholdersEquity, NetCashProvidedByUsedInOperatingActivities; 6 discontinued-operations lines changed; bucket: discontinued-operations recast
   - changed same-year currency lines: CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations, CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations, CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations, ComprehensiveIncomeNetOfTax, ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentIncomeTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, Depreciation, DepreciationAmortizationAndAccretionNet +53 more
   - filings (10-Qs left out): 2018-02-23 10-K NetCashProvidedByUsedInInvestingActivities 2,322.0M USD; 2018-02-23 10-K NetCashProvidedByUsedInInvestingActivitiesContinuingOperations 3,940.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInInvestingActivities 6,564.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInInvestingActivitiesContinuingOperations 8,348.0M USD; 2020-02-24 10-K NetCashProvidedByUsedInInvestingActivities 5,379.0M USD; 2020-02-24 10-K NetCashProvidedByUsedInInvestingActivitiesContinuingOperations 6,728.0M USD
15. **MS operating_cash_flow FY2016** (period end 2016-12-31), gap 119.98%
   - own: 2,447.0M USD, NetCashProvidedByUsedInOperatingActivitiesContinuingOperations, 10-K 0001193125-17-059212 filed 2017-02-27
   - shown: 5,383.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0001193125-19-051943 filed 2019-02-26 (FY2018 report)
   - evidence: tag changed NetCashProvidedByUsedInOperatingActivitiesContinuingOperations -> NetCashProvidedByUsedInOperatingActivities; no us-gaap tag in either filing carries the other's value; 9/118 shared same-year currency lines changed, net income unchanged; bucket: own value under another tag of the concept
   - changed same-year currency lines: CashAndCashEquivalentsAtCarryingValue, CashAndCashEquivalentsPeriodIncreaseDecrease, EffectOfExchangeRateOnCashAndCashEquivalents, IncreaseDecreaseInAccountsPayable, IncreaseDecreaseInFinancialInstrumentsUsedInOperatingActivities, IncreaseDecreaseInReceivables, OtherNoncashIncomeExpense, ProceedsFromPaymentsForOtherFinancingActivities, UnrecognizedTaxBenefitsThatWouldImpactEffectiveTaxRate
   - filings (10-Qs left out): 2017-02-27 10-K NetCashProvidedByUsedInOperatingActivitiesContinuingOperations 2,447.0M USD; 2018-02-27 10-K NetCashProvidedByUsedInOperatingActivities 5,383.0M USD; 2019-02-26 10-K NetCashProvidedByUsedInOperatingActivities 5,383.0M USD
16. **CVS net_interest_income FY2016** (period end 2016-12-31), gap 100.00%
   - own: -1,058.0M USD, InterestIncomeExpenseNet, 10-K 0000064803-17-000006 filed 2017-02-09
   - shown: 0 USD, InterestIncomeExpenseNet, 8-K 0000064803-19-000042 filed 2019-08-08
   - evidence: no us-gaap tag in either filing carries the other's value; 9/70 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss, NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged
   - changed same-year currency lines: IncreaseDecreaseInOtherOperatingLiabilities, InterestIncomeExpenseNet, NetCashProvidedByUsedInFinancingActivities, NetCashProvidedByUsedInOperatingActivities, OperatingExpenses, OperatingIncomeLoss, PaymentsToAcquireBusinessesNetOfCashAcquired, PaymentsToSuppliersAndEmployees, ProceedsFromStockOptionsExercised
   - filings (10-Qs left out): 2017-02-09 10-K InterestIncomeExpenseNet -1,058.0M USD; 2018-02-14 10-K InterestIncomeExpenseNet -1,058.0M USD; 2019-08-08 8-K InterestIncomeExpenseNet 0 USD
17. **CVS net_interest_income FY2017** (period end 2017-12-31), gap 100.00%
   - own: -1,041.0M USD, InterestIncomeExpenseNet, 10-K 0001558370-18-000707 filed 2018-02-14
   - shown: 0 USD, InterestIncomeExpenseNet, 10-K 0000064803-20-000007 filed 2020-02-18 (FY2019 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 8/74 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: AllowanceForDoubtfulAccountsReceivable, IncreaseDecreaseInOtherOperatingAssets, IncreaseDecreaseInOtherOperatingLiabilities, InterestIncomeExpenseNet, NetCashProvidedByUsedInInvestingActivities, OperatingExpenses, OperatingIncomeLoss, PaymentsToAcquireBusinessesNetOfCashAcquired
   - filings (10-Qs left out): 2018-02-14 10-K InterestIncomeExpenseNet -1,041.0M USD; 2019-08-08 8-K InterestIncomeExpenseNet 0 USD; 2020-02-18 10-K InterestIncomeExpenseNet 0 USD
18. **FDX net_income FY2026** (period end 2026-05-31), gap 100.00%
   - own: 4,433.0M USD, NetIncomeLoss, 10-K 0001048911-26-000105 filed 2026-07-20
   - shown: 4,433 USD, NetIncomeLoss, DEF 14A 0001104659-26-097836 filed 2026-08-17
   - evidence: no us-gaap tag in either filing carries the other's value; 1/1 shared same-year currency lines changed, net income changed; headline lines changed: NetIncomeLoss; bucket: shown value from a proxy statement
   - changed same-year currency lines: NetIncomeLoss
   - filings (10-Qs left out): 2026-07-20 10-K NetIncomeLoss 4,433.0M USD; 2026-07-20 10-K NetIncomeLossAvailableToCommonStockholdersBasic 4,426.0M USD; 2026-08-17 DEF 14A NetIncomeLoss 4,433 USD
19. **FDX net_income FY2024** (period end 2024-05-31), gap 100.00%
   - own: 4,331.0M USD, NetIncomeLoss, 10-K 0000950170-24-083577 filed 2024-07-15
   - shown: 4,331 USD, NetIncomeLoss, DEF 14A 0001104659-26-097836 filed 2026-08-17
   - evidence: no us-gaap tag in either filing carries the other's value; 1/1 shared same-year currency lines changed, net income changed; headline lines changed: NetIncomeLoss; bucket: shown value from a proxy statement
   - changed same-year currency lines: NetIncomeLoss
   - filings (10-Qs left out): 2024-07-15 10-K NetIncomeLoss 4,331.0M USD; 2024-07-15 10-K NetIncomeLossAvailableToCommonStockholdersBasic 4,325.0M USD; 2024-07-15 10-K ProfitLoss 4,331.0M USD; 2025-07-21 10-K NetIncomeLoss 4,331.0M USD; 2025-07-21 10-K NetIncomeLossAvailableToCommonStockholdersBasic 4,325.0M USD; 2026-07-20 10-K NetIncomeLoss 4,331.0M USD; 2026-07-20 10-K NetIncomeLossAvailableToCommonStockholdersBasic 4,325.0M USD; 2026-08-17 DEF 14A NetIncomeLoss 4,331 USD
20. **PLD operating_income FY2018** (period end 2018-12-31), gap 99.29%
   - own: 847.0M USD, OperatingIncomeLoss, 10-K 0001564590-19-002872 filed 2019-02-13
   - shown: 1,688.0M USD, OperatingIncomeLoss, 10-K 0001564590-21-005312 filed 2021-02-11 (FY2020 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 4/88 shared same-year currency lines changed, net income unchanged; headline lines changed: OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: LineOfCreditFacilityRemainingBorrowingCapacity, NonoperatingIncomeExpense, OperatingIncomeLoss, OperatingLeasesIncomeStatementLeaseRevenue
   - filings (10-Qs left out): 2019-02-13 10-K OperatingIncomeLoss 847.0M USD; 2020-02-11 10-K OperatingIncomeLoss 1,688.0M USD; 2021-02-11 10-K OperatingIncomeLoss 1,688.0M USD
21. **MS cash_and_equivalents FY2016** (period end 2016-12-31), gap 78.33%
   - own: 43,381.0M USD, CashAndCashEquivalentsAtCarryingValue, 10-K 0001193125-17-059212 filed 2017-02-27
   - shown: 77,360.0M USD, CashAndCashEquivalentsAtCarryingValue, 10-K 0001193125-19-051943 filed 2019-02-26 (FY2018 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 9/118 shared same-year currency lines changed, net income unchanged; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CashAndCashEquivalentsAtCarryingValue, CashAndCashEquivalentsPeriodIncreaseDecrease, EffectOfExchangeRateOnCashAndCashEquivalents, IncreaseDecreaseInAccountsPayable, IncreaseDecreaseInFinancialInstrumentsUsedInOperatingActivities, IncreaseDecreaseInReceivables, OtherNoncashIncomeExpense, ProceedsFromPaymentsForOtherFinancingActivities, UnrecognizedTaxBenefitsThatWouldImpactEffectiveTaxRate
   - filings (10-Qs left out): 2017-02-27 10-K CashAndCashEquivalentsAtCarryingValue 43,381.0M USD; 2018-02-27 10-K CashAndCashEquivalentsAtCarryingValue 77,360.0M USD; 2019-02-26 10-K CashAndCashEquivalentsAtCarryingValue 77,360.0M USD; 2020-02-27 10-K CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents 77,360.0M USD
22. **UPS operating_income FY2016** (period end 2016-12-31), gap 40.63%
   - own: 5,467.0M USD, OperatingIncomeLoss, 10-K 0001090727-17-000011 filed 2017-02-21
   - shown: 7,688.0M USD, OperatingIncomeLoss, 10-K 0001090727-19-000006 filed 2019-02-21 (FY2018 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 22/75 shared same-year currency lines changed, net income changed; headline lines changed: OperatingIncomeLoss, NetIncomeLoss, Assets; bucket: broad recast, net income changed
   - changed same-year currency lines: Assets, ComprehensiveIncomeNetOfTax, CostsAndExpenses, DeferredFederalIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredIncomeTaxesAndTaxCredits, DeferredStateAndLocalIncomeTaxExpenseBenefit, IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic, IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments, IncomeTaxExpenseBenefit, IncreaseDecreaseInAccountsPayable, IncreaseDecreaseInEmployeeRelatedLiabilities, IncreaseDecreaseInOtherOperatingAssets, IncreaseDecreaseInOtherOperatingLiabilities, InvestmentIncomeNonoperating +7 more
   - filings (10-Qs left out): 2017-02-21 10-K OperatingIncomeLoss 5,467.0M USD; 2018-02-21 10-K OperatingIncomeLoss 5,467.0M USD; 2019-02-21 10-K OperatingIncomeLoss 7,688.0M USD
23. **GS operating_cash_flow FY2020** (period end 2020-12-31), gap 35.02%
   - own: -13,728.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0001193125-21-049380 filed 2021-02-22
   - shown: -18,535.0M USD, NetCashProvidedByUsedInOperatingActivities, 10-K 0000886982-23-000003 filed 2023-02-24 (FY2022 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 4/82 shared same-year currency lines changed, net income unchanged; headline lines changed: NetCashProvidedByUsedInOperatingActivities; bucket: broad recast, net income unchanged
   - changed same-year currency lines: BrokerageCommissionsRevenue, IncreaseDecreaseInOtherOperatingCapitalNet, InvestmentBankingRevenue, NetCashProvidedByUsedInOperatingActivities
   - filings (10-Qs left out): 2021-02-22 10-K NetCashProvidedByUsedInOperatingActivities -13,728.0M USD; 2022-02-25 10-K NetCashProvidedByUsedInOperatingActivities -13,728.0M USD; 2023-02-24 10-K NetCashProvidedByUsedInOperatingActivities -18,535.0M USD
24. **BA current_liabilities FY2017** (period end 2017-12-31), gap 32.66%
   - own: 56,269.0M USD, LiabilitiesCurrent, 10-K 0000012927-18-000007 filed 2018-02-12
   - shown: 74,648.0M USD, LiabilitiesCurrent, 10-K 0000012927-19-000010 filed 2019-02-08 (FY2018 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 64/222 shared same-year currency lines changed, net income changed; headline lines changed: Revenues, CostOfRevenue, OperatingIncomeLoss, NetIncomeLoss, Assets, StockholdersEquity; bucket: broad recast, net income changed
   - changed same-year currency lines: AccountsReceivableNetCurrent, AccruedLiabilitiesCurrent, AccumulatedOtherComprehensiveIncomeLossNetOfTax, Assets, AssetsCurrent, AvailableForSaleSecurities, CashAndCashEquivalentsPeriodIncreaseDecrease, ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest, CostOfRevenue, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredIncomeTaxLiabilities, DeferredStateAndLocalIncomeTaxExpenseBenefit, DeferredTaxAssetsGross +49 more
   - filings (10-Qs left out): 2018-02-12 10-K LiabilitiesCurrent 56,269.0M USD; 2019-02-08 10-K LiabilitiesCurrent 74,648.0M USD
25. **T operating_income FY2020** (period end 2020-12-31), gap 30.71%
   - own: 6,405.0M USD, OperatingIncomeLoss, 10-K 0000732717-21-000012 filed 2021-02-25
   - shown: 8,372.0M USD, OperatingIncomeLoss, 10-K 0000732717-23-000011 filed 2023-02-13 (FY2022 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 63/115 shared same-year currency lines changed, net income unchanged; headline lines changed: Revenues, OperatingIncomeLoss; bucket: broad recast, net income unchanged
   - changed same-year currency lines: AdjustmentsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivities, AdvertisingExpense, AllocatedShareBasedCompensationExpense, CashAndCashEquivalentsAtCarryingValue, CostsAndExpenses, CurrentFederalTaxExpenseBenefit, CurrentForeignTaxExpenseBenefit, CurrentStateAndLocalTaxExpenseBenefit, DeferredFederalIncomeTaxExpenseBenefit, DeferredForeignIncomeTaxExpenseBenefit, DeferredIncomeTaxExpenseBenefit, DeferredStateAndLocalIncomeTaxExpenseBenefit, DefinedContributionPlanCostRecognized, Depreciation, DepreciationDepletionAndAmortization +48 more
   - filings (10-Qs left out): 2021-02-25 10-K OperatingIncomeLoss 6,405.0M USD; 2021-06-21 8-K OperatingIncomeLoss 6,405.0M USD; 2022-02-16 10-K OperatingIncomeLoss 6,405.0M USD; 2023-02-13 10-K OperatingIncomeLoss 8,372.0M USD

## Companies with the most cells over 1% (across)

| ticker | cells > 1% | concepts |
|---|---|---|
| GE | 63 | revenue 7, capital_expenditures 7, earnings_per_share 6, eps_diluted 6, operating_cash_flow 5, total_assets 5, cash_and_equivalents 5, net_income 4, financing_cash_flow 4, shareholders_equity 4, current_assets 4, current_liabilities 4, investing_cash_flow 2 |
| T | 20 | operating_income 4, capital_expenditures 4, cash_and_equivalents 3, revenue 2, operating_cash_flow 2, investing_cash_flow 2, eps_diluted 1, current_assets 1, current_liabilities 1 |
| PFE | 18 | revenue 4, capital_expenditures 3, net_income 2, operating_cash_flow 2, financing_cash_flow 2, earnings_per_share 2, eps_diluted 2, cash_and_equivalents 1 |
| KO | 17 | gross_profit 2, operating_income 2, capital_expenditures 2, investing_cash_flow 2, cash_and_equivalents 2, current_assets 2, current_liabilities 2, revenue 1, operating_cash_flow 1, financing_cash_flow 1 |
| AMD | 16 | investing_cash_flow 3, revenue 2, operating_cash_flow 2, shareholders_equity 2, net_income 1, gross_profit 1, operating_income 1, financing_cash_flow 1, earnings_per_share 1, eps_diluted 1, current_liabilities 1 |
| BA | 15 | net_income 2, gross_profit 2, operating_income 2, earnings_per_share 2, eps_diluted 2, revenue 1, total_assets 1, shareholders_equity 1, current_assets 1, current_liabilities 1 |
| HON | 14 | revenue 2, capital_expenditures 2, cash_and_equivalents 2, long_term_debt 2, net_income 1, gross_profit 1, operating_income 1, earnings_per_share 1, eps_diluted 1, shareholders_equity 1 |
| LMT | 13 | net_income 2, gross_profit 2, operating_income 2, earnings_per_share 2, eps_diluted 2, revenue 1, shareholders_equity 1, current_liabilities 1 |
| CVS | 13 | financing_cash_flow 3, net_income 2, earnings_per_share 2, eps_diluted 2, net_interest_income 2, operating_income 1, investing_cash_flow 1 |
| TSLA | 13 | earnings_per_share 4, eps_diluted 4, net_income 2, investing_cash_flow 2, long_term_debt 1 |
| CRM | 12 | net_income 2, operating_income 2, earnings_per_share 2, eps_diluted 2, shareholders_equity 2, total_assets 1, current_assets 1 |
| VZ | 11 | net_income 5, operating_cash_flow 2, investing_cash_flow 2, operating_income 1, financing_cash_flow 1 |
| MSFT | 10 | revenue 1, net_income 1, gross_profit 1, operating_income 1, earnings_per_share 1, eps_diluted 1, total_assets 1, shareholders_equity 1, current_assets 1, current_liabilities 1 |
| LLY | 10 | revenue 3, operating_cash_flow 2, investing_cash_flow 2, cash_and_equivalents 2, long_term_debt 1 |
| INTC | 10 | investing_cash_flow 3, financing_cash_flow 3, operating_cash_flow 2, operating_income 1, current_assets 1 |
| ORCL | 10 | net_income 2, operating_income 2, earnings_per_share 2, eps_diluted 2, revenue 1, shareholders_equity 1 |
| GS | 10 | operating_cash_flow 5, investing_cash_flow 3, financing_cash_flow 1, noninterest_income 1 |
| GM | 10 | revenue 3, net_income 3, operating_income 2, capital_expenditures 1, cash_and_equivalents 1 |
| JPM | 9 | operating_cash_flow 4, investing_cash_flow 3, noninterest_income 2 |
| BAC | 9 | noninterest_income 4, operating_cash_flow 2, net_interest_income 2, investing_cash_flow 1 |
| AMZN | 8 | investing_cash_flow 2, earnings_per_share 2, eps_diluted 2, operating_cash_flow 1, financing_cash_flow 1 |
| NVDA | 8 | earnings_per_share 4, eps_diluted 4 |
| FDX | 8 | net_income 5, operating_income 2, long_term_debt 1 |
| NEE | 8 | operating_income 2, financing_cash_flow 2, earnings_per_share 2, eps_diluted 2 |
| AAPL | 6 | financing_cash_flow 2, earnings_per_share 2, eps_diluted 2 |
| GOOGL | 6 | earnings_per_share 2, eps_diluted 2, operating_income 1, long_term_debt 1 |
| IBM | 6 | gross_profit 3, revenue 2, financing_cash_flow 1 |
| CVX | 5 | investing_cash_flow 2, cash_and_equivalents 2, operating_cash_flow 1 |
| JNJ | 5 | revenue 2, gross_profit 2, cash_and_equivalents 1 |
| MRK | 5 | revenue 2, capital_expenditures 2, net_income 1 |
| UPS | 5 | revenue 2, operating_income 1, current_assets 1, current_liabilities 1 |
| AXP | 5 | noninterest_income 2, cash_and_equivalents 2, investing_cash_flow 1 |
| F | 5 | net_income 2, earnings_per_share 1, eps_diluted 1, shareholders_equity 1 |
| TGT | 5 | revenue 2, gross_profit 1, total_assets 1, current_liabilities 1 |
| PEP | 4 | operating_income 1, operating_cash_flow 1, financing_cash_flow 1, current_assets 1 |
| WMT | 4 | earnings_per_share 2, eps_diluted 2 |
| NFLX | 4 | earnings_per_share 2, eps_diluted 2 |
| CAT | 4 | operating_income 2, investing_cash_flow 2 |
| DUK | 4 | operating_income 3, long_term_debt 1 |
| SBUX | 4 | operating_cash_flow 2, financing_cash_flow 2 |
| PG | 3 | operating_income 2, investing_cash_flow 1 |
| PLD | 3 | operating_income 2, long_term_debt 1 |
| MS | 3 | operating_cash_flow 1, noninterest_income 1, cash_and_equivalents 1 |
| V | 3 | operating_cash_flow 2, financing_cash_flow 1 |
| MA | 3 | operating_cash_flow 2, financing_cash_flow 1 |
| REGN | 2 | revenue 2 |
| NKE | 2 | operating_cash_flow 1, financing_cash_flow 1 |
| MCD | 2 | revenue 2 |
| LOW | 2 | gross_profit 2 |
| HD | 1 | financing_cash_flow 1 |
| DE | 1 | investing_cash_flow 1 |
| ADBE | 1 | financing_cash_flow 1 |

## Worked case: REGN revenue

- REGN revenue FY2016: own = shown (4,860.4M USD)
- REGN revenue FY2017: own = shown (5,872.2M USD)
0. **REGN revenue FY2018** (period end 2018-12-31), gap 23.32%
   - own: 6,710.8M USD, RevenueFromContractWithCustomerExcludingAssessedTax, 10-K 0001532176-19-000009 filed 2019-02-07
   - shown: 5,145.6M USD, RevenueFromContractWithCustomerExcludingAssessedTax, 10-K 0001804220-21-000008 filed 2021-02-08 (FY2020 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 8/57 shared same-year currency lines changed, net income unchanged; headline lines changed: RevenueFromContractWithCustomerExcludingAssessedTax; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CostsAndExpenses, IncreaseDecreaseInAccountsPayableAndAccruedLiabilities, IncreaseDecreaseInAccountsReceivable, IncreaseDecreaseInContractWithCustomerLiability, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets, ResearchAndDevelopmentExpense, RevenueFromContractWithCustomerExcludingAssessedTax, SellingGeneralAndAdministrativeExpense
   - filings (10-Qs left out): 2019-02-07 10-K RevenueFromContractWithCustomerExcludingAssessedTax 6,710.8M USD; 2020-02-07 10-K RevenueFromContractWithCustomerExcludingAssessedTax 6,710.8M USD; 2021-02-08 10-K RevenueFromContractWithCustomerExcludingAssessedTax 5,145.6M USD
0. **REGN revenue FY2019** (period end 2019-12-31), gap 16.61%
   - own: 7,863.4M USD, RevenueFromContractWithCustomerExcludingAssessedTax, 10-K 0001532176-20-000008 filed 2020-02-07
   - shown: 6,557.6M USD, RevenueFromContractWithCustomerExcludingAssessedTax, 10-K 0001804220-22-000007 filed 2022-02-07 (FY2021 report)
   - evidence: no us-gaap tag in either filing carries the other's value; 9/62 shared same-year currency lines changed, net income unchanged; headline lines changed: RevenueFromContractWithCustomerExcludingAssessedTax; bucket: broad recast, net income unchanged
   - changed same-year currency lines: CostsAndExpenses, IncreaseDecreaseInAccountsPayableAndAccruedLiabilities, IncreaseDecreaseInAccountsReceivable, IncreaseDecreaseInContractWithCustomerLiability, IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets, OtherNoncashIncomeExpense, ResearchAndDevelopmentExpense, RevenueFromContractWithCustomerExcludingAssessedTax, SellingGeneralAndAdministrativeExpense
   - filings (10-Qs left out): 2020-02-07 10-K RevenueFromContractWithCustomerExcludingAssessedTax 7,863.4M USD; 2021-02-08 10-K RevenueFromContractWithCustomerExcludingAssessedTax 6,557.6M USD; 2022-02-07 10-K RevenueFromContractWithCustomerExcludingAssessedTax 6,557.6M USD
- REGN revenue FY2020: own = shown (8,497.1M USD)
- REGN revenue FY2021: own = shown (16,071.7M USD)
- REGN revenue FY2022: own = shown (12,172.9M USD)
- REGN revenue FY2023: own = shown (13,117.2M USD)
- REGN revenue FY2024: own = shown (14,202.0M USD)

---

# Analyst reading (added by hand after the run; not script output)

## The 25 largest gaps, read one by one

| # | case | reading | kind |
|---|---|---|---|
| 1 | TSLA long_term_debt FY2016, 5.9M -> 5,892.0M | Exactly x1000: the FY2016 10-K's XBRL scaled LongTermDebt wrong; the FY2017 10-K carries the right figure. | XBRL error in the own filing |
| 2-5 | GE EPS basic/diluted FY2019 and FY2020, -0.62 -> -4.99, 0.58 -> 4.64 | Exactly x8: the 1-for-8 reverse split (2021); FY2020's 4.63 -> 4.64 is the 2023 8-K recast for the GE HealthCare spin. | per-share split basis |
| 6 | GS operating_cash_flow FY2021, 921M -> 6,298M | The FY2022 10-K moved FY2021 operating cash flow (and FY2020, -13,728M -> -18,535M); net income unchanged, 5 of 80 lines moved. A cash-flow classification revision; companyfacts cannot show whether GS called it an error correction. | cash-flow reclassification |
| 7 | GE operating_cash_flow FY2016, -244M -> 1,160M | FY2018 10-K: ASC 606 full-retrospective adoption plus discontinued-operations recasts; net income moved. | accounting change + disc-ops recast |
| 8, 10 | JPM investing/operating cash flow FY2017 | FY2018 10-K: retrospective adoption of the cash-flow standards (ASU 2016-18 restricted cash, with deposits with banks moved into cash; ASU 2016-15); net income unchanged. | accounting change (presentation) |
| 9 | BA shareholders_equity FY2017, 355M -> 1,656M | FY2018 10-K: ASC 606 full-retrospective adoption; revenue, costs, net income and equity all moved. | accounting change |
| 11 | CRM operating_income FY2017, 64.2M -> 218.0M | FY2019 10-K: ASC 606 full retrospective (with the contract-cost capitalisation it brought). | accounting change |
| 12-13 | AMD financing/investing cash flow FY2021, -1,895M -> +1,895M, -686M -> +686M | Exact sign flips in the FY2023 10-K's comparatives; AMD used cash in both in 2021. The shown value is the wrong one. | XBRL sign error in the later filing |
| 14, 17 | GE EPS diluted/basic FY2022, -0.05/-0.06 -> 0.05 | 2023 recasts: LDTI (ASU 2018-12) applied retrospectively plus the GE HealthCare and GE Vernova discontinued-operations recasts; net income moved. | accounting change + disc-ops recast |
| 15, 18, 19 | CRM FY2018 EPS diluted, net income, EPS basic (127.5M -> 360.0M) | FY2019 10-K: ASC 606 full retrospective. | accounting change |
| 16 | T current_assets FY2021, 59,997M -> 170,768M | FY2022 10-K: WarnerMedia presented as discontinued operations in the 2021 balance sheet; revenue and operating income moved, net income did not. (The "LongTermDebt..." match is a coincidence.) | disc-ops recast |
| 20-22 | AMD FY2017 net income 43M -> -33M, EPS 0.04 -> -0.03 | FY2018 10-K: ASC 606 full retrospective. (The re-tag hint on #20 is a coincidental match.) | accounting change |
| 23 | PLD operating_income FY2017, 771.1M -> 1,954.0M | FY2019 10-K: a presentation change that moved development-disposition gains into operating income (4 of 85 lines, net income unchanged); FY2018 moved the same way (847M -> 1,688M). | presentation reclassification |
| 24 | CAT operating_income FY2016, 498M -> 1,162M | FY2018 10-K: ASU 2017-07, which moved non-service pension and OPEB cost (CAT's 2016 mark-to-market loss) out of operating profit. | accounting change (presentation) |
| 25 | GE investing_cash_flow FY2017, 2,322M -> 5,379M | Successive recasts (FY2018: 6,564M; FY2019: 5,379M): ASC 606 retrospective plus discontinued operations. | accounting change + disc-ops recast |

Tally: an error restatement under ASC 250 is visible in none of the 25. Fifteen are retrospective accounting changes or discontinued-operations recasts, four are a split basis, three are XBRL errors (one in the own filing, two in the later one), and three are reclassifications (GS, PLD, T). No 10-K/A replaced any value in the 8,616 cells.

## Findings for the design

1. **Size.** The own value differs from what ingest shows above 1% in 438 of 8,616 cells (5.1%; 5.5% of the 7,892 cells a later filing supplied), at 52 of 59 companies. Without per-share: 353 cells. The counts at 0.1/0.5/1/2/5% are 649/523/438/355/246.
2. **Rounding noise sits below 0.1%.** 119 of the 120 rounding-only gaps fall at or below 0.2%, almost all at or below 0.05%. Between 0.1% and 1% sit 211 cells, of which 4 are rounding: these are real small changes (reclassifications, proxy values rounded to $0.1B, cents of EPS). The histogram has no knee, so the tolerance is a materiality choice, not a noise floor.
3. **Tags.** 222 later-filing cells (2.8%) have the own report only under another tag; 34 of the 438 gaps over 1% need an across-tag lookup to be found. Of those 34, 23 are false: 8 are tag-priority artifacts where the later filing reports the identical own value under the own tag (AXP, CVX, F, GM, PFE), 13 compare a continuing-operations cash-flow subtotal with a total (AAPL, BAC, CAT, GS, MS, TSLA), and 2 compare long-term debt with its noncurrent part (FDX, GOOGL). The other 11 are real, from ASC 606-era revenue tag moves (SalesRevenueNet/Revenues -> RevenueFromContract...: AMD, LMT, MSFT, ORCL, TGT, UPS) and GE's Revenues/RevenueFromContract... scope mismatch. The within-tag lookup misses nothing the across-tag one finds, except those 34.
4. **Ingest bug, separate from WP5.** Companyfacts winners are the latest-filed item of any form. Since 2023, proxy statements' pay-versus-performance tables tag NetIncomeLoss for five years and are filed after the 10-K. 120 cells (24 of 59 companies, net income FY2021-FY2026) take their value from a DEF 14A or a PRE 14C. Twelve of those companies differ from the 10-K: FDX at 1/1,000,000 scale (net income stored as $3,826 to $4,433), MRK up to 5.4%, VZ 4.1%, GM 3.1%, TSLA 2.3%, CVX up to 0.2% (rounded to $0.1B), and CAT, HD, JPM, MCD, ORCL and NFLX smaller. Companyfacts rows skip reconcile_facts, so nothing flags them.
5. **REGN.** FY2019's shown 6,557.6M comes from the FY2021 10-K (0001804220-22-000007, the latest filer), not the FY2020 10-K that first reported it. The FY2020 10-K carries no us-gaap tag with 6,710.8M for FY2018: the total moved to an extension tag, and RevenueFromContract... now holds the narrower ASC 606 revenue. Only RevenueFromContract... (8 of 57 lines) moved, and net income did not. This is a scope change, not a restatement.
