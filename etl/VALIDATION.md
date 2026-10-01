# Milestone 3 local validation — 2026-10-01

These are measurements from this Windows workspace using the existing Python 3.13 environment. They are not universal performance claims. Other validation work ran concurrently during parts of the benchmarks.

Official source: [UCI Online Retail II, dataset 502](https://archive.ics.uci.edu/dataset/502/online+retail+ii). Workbook: `online_retail_II.xlsx`.

Source SHA-256: `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`.

## Raw profile

| Worksheet | Rows |
|---|---:|
| Year 2009-2010 | 525,461 |
| Year 2010-2011 | 541,910 |
| Total | 1,067,371 |

| Column | Observed Python cell types and counts | Missing |
|---|---|---:|
| Invoice | int: 1,047,871, str: 19,500 | 0 |
| StockCode | int: 932,385, str: 134,986 | 0 |
| Description | str: 1,062,985, NoneType: 4,382, int: 4 | 4,382 |
| Quantity | int: 1,067,371 | 0 |
| InvoiceDate | datetime: 1,067,371 | 0 |
| Price | float: 1,057,347, int: 10,024 | 0 |
| Customer ID | int: 824,364, NoneType: 243,007 | 243,007 |
| Country | str: 1,067,371 | 0 |

| Raw observation | Rows |
|---|---:|
| Duplicate occurrences after first | 34,335 |
| missing_customer_ids | 243,007 |
| invalid_customer_ids | 0 |
| cancelled_transactions | 19,494 |
| invalid_invoice_ids | 6 |
| invalid_product_codes | 0 |
| invalid_dates | 0 |
| invalid_quantities | 0 |
| negative_quantities | 22,950 |
| zero_quantities | 0 |
| invalid_prices | 0 |
| negative_prices | 5 |
| zero_prices | 6,202 |
| missing_descriptions | 4,382 |
| missing_countries | 0 |

Raw distinct nonmissing values: Customer ID: 5,942; Invoice: 53,628; StockCode: 5,304; Country: 43.

Raw timestamp range: **2009-12-01T07:45:00** to **2011-12-09T12:50:00**. All source dates parsed; timezone unspecified.

Countries/source labels: Australia, Austria, Bahrain, Belgium, Bermuda, Brazil, Canada, Channel Islands, Cyprus, Czech Republic, Denmark, EIRE, European Community, Finland, France, Germany, Greece, Hong Kong, Iceland, Israel, Italy, Japan, Korea, Lebanon, Lithuania, Malta, Netherlands, Nigeria, Norway, Poland, Portugal, RSA, Saudi Arabia, Singapore, Spain, Sweden, Switzerland, Thailand, USA, United Arab Emirates, United Kingdom, Unspecified, West Indies.

## Rules and exclusions

The [ETL documentation](README.md) defines the full policy. Every source occurrence remains in staging. Missing customers, exact duplicates, signed returns/cancellations, and missing descriptions are retained when other eligibility rules pass. No customer IDs are invented.

| Primary exclusion reason (disjoint) | Rows |
|---|---:|
| business:zero_prices | 6,202 |
| quality:invalid_invoice_ids | 6 |

Overlapping exclusion counts: business:zero_prices: 6,202; quality:invalid_invoice_ids: 6; business:negative_prices: 5.

The five negative-price rows overlap with the six unsupported A-prefixed invoice rows. They are not an additional five excluded rows. Unsupported formats remain visible rather than being assumed corrupt.

## Repeat execution and dimensions

| Table | Run 1 | Run 2 |
|---|---:|---:|
| staging_transaction | 1,067,371 | 1,067,371 |
| fact_transaction | 1,061,163 | 1,061,163 |
| dim_customer | 5,939 | 5,939 |
| dim_product | 4,930 | 4,930 |
| dim_date | 604 | 604 |
| dim_country | 43 | 43 |

Accounting on both runs: **1,067,371 = 1,061,163 eligible + 6,208 excluded**.

Fact grain: one eligible source worksheet row occurrence. Composite primary key `(source_sheet, source_row)` prevents replay duplication while retaining genuine repeated source occurrences. Dimensions use unique natural keys; date keys are YYYYMMDD. See [schema.sql](schema.sql).

## Reconciliation

- Both runs passed raw/staging/fact accounting, row-level field agreement, unique dimension/fact keys, dimension coverage, foreign-key checks, SQLite integrity, and exact integer amount arithmetic.
- Foreign-key violations: **0**. Staging/fact row mismatches: **0**.
- Fact timestamp range matches the raw range. A separate date-dimension link query found **0** timestamp/date-key mismatches.
- Fact distinct invoices: **48,368**; known customers: **5,939**; anonymous rows: **236,870**.
- Exact signed line amount sum: **19,434,864,648,000 GBP millionths** (quantity × source unit price, not an audited revenue claim).
- Eligible cancellation lines: **19,494**; eligible negative-quantity lines: **19,493**. Source signs are retained, including the cancellation line with positive quantity.
- **623** eligible product codes have multiple description values; all source descriptions remain in staging. The product dimension stores a deterministic representative, not historical product attributes.
- Both run reports match the independently executed pre-transformation raw profile, including SHA-256, worksheet counts, flags, types, missing values, distinct keys, and dates.

## Local measurements

| Measurement | Run 1 | Run 2 |
|---|---:|---:|
| elapsed_etl_seconds | 114.672 | 142.246 |
| database_bytes | 758,206,464 | 758,206,464 |
| peak_process_working_set_bytes | 261,718,016 | 260,685,824 |

The database contains every staging raw payload as well as analytical tables and indexes, explaining its size. Peak memory is the Windows process peak working set. Separate benchmark JSON reports remain local under `data/processed/`.

## Regression checks and boundaries

- **38 tests passed**: 22 existing Telco/page tests plus 16 retail synthetic tests. Fixtures are temporary workbooks/databases; the full dataset is not required for unit tests.
- `python -m compileall analytics etl frontend ml backend`: passed.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed.
- Existing Telco ingestion: **7,043** source/stored customers, **11** missing total charges, zero blocking quality findings.
- Existing Analytics page AppTest with actual local data: no exception; **7,043** customers and **1,869** observed churn cases displayed.
- Streamlit headless startup passed; health endpoint returned **HTTP 200, ok**. Validation server stopped afterward.
- Existing comparison-component Streamlit deprecation notices remain; no retail UI was introduced.
- Raw workbooks/archive, SQLite databases, and generated JSON outputs are ignored. No model artifacts changed. Nothing was pushed, merged, published, or deployed.

Remaining limitations: single-writer full-snapshot rebuild; source-position keys do not survive workbook reordering as event IDs; duplicate retention requires explicit policy in future analyses; anonymous transactions cannot support identified-customer retention; descriptions are not slowly changing dimensions; no source timezone; positive-price analytical scope excludes free items and special adjustments. Retail has no churn label and is never joined to Telco.
