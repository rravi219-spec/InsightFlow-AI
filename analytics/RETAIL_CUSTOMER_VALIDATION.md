# Milestone 4 measured validation — 2026-10-01

Branch: `feature/sql-customer-analytics`. This report records actual local outputs from the validated Online Retail II SQLite database. These are descriptive associations, not causal or business-impact claims. The [methodology](RETAIL_CUSTOMER_ANALYTICS.md) defines every population, denominator, and rule.

## Scope and populations

- Qualifying behavior: known customer, positive quantity, non-cancelled line, already accepted by the retail ETL.
- Every signed known-customer adjustment stays in the value ledger. Anonymous transactions have no fabricated identities.
- Existing ETL exclusions and duplicate-retention policy remain unchanged. Multiple purchase lines per customer/invoice count as one order.

## Executive metrics

| Metric | Measured value |
|---|---:|
| known_analytical_customers | 5,878 |
| purchase_invoices | 36,969 |
| repeat_customers | 4,255 |
| one_time_customers | 1,623 |
| repeat_purchase_rate_pct | 72.38856754 |
| average_purchase_frequency | 6.2893841443 |
| first_purchase_date | 2009-12-01 |
| last_purchase_date | 2011-12-09 |
| known_ledger_customers | 5,939 |
| eligible_transaction_lines | 824,293 |
| gross_purchase_micros | 17,743,429,178,000 GBP millionths (= 17,743,429.178 GBP) |
| return_signed_micros | -1,095,136,790,000 GBP millionths (= -1,095,136.79 GBP) |
| net_value_micros | 16,648,292,388,000 GBP millionths (= 16,648,292.388 GBP) |
| average_customer_value_gbp | 2,803.2147479374 |
| return_cancellation_deduction_micros | 1,095,136,790,000 GBP millionths (= 1,095,136.79 GBP) |
| average_order_value_gbp | 479.9542637886 |
| return_only_customers | 61 |
| anonymous_lines | 236,870 |
| positive_cancellation_lines | 0 |

Behavioral customer counts exclude 61 return-only customers. The executive net total includes those customers; its denominator for average customer value is 5,939 known ledger customers. All 236,870 anonymous fact lines are outside customer-level metrics.

## RFM methodology and actual distribution

Analysis/reference date: **2011-12-10**, one day after the final fact date. R = days since last purchase; F = distinct customer/invoice purchase count; M = gross qualifying purchase value. Scores use midpoint ranks for ties, mapped to 1–5. Equal values are not split; singleton/all-equal metrics receive 3. Rules and CASE precedence are documented in the methodology.

| Metric | Minimum | Maximum | Distinct values | Largest tie |
|---|---:|---:|---:|---:|
| recency_days | 1 | 739 | 593 | 103 |
| frequency | 1 | 398 | 90 | 1,623 |
| monetary_micros | 2,950,000 | 608,821,650,000 | 5,767 | 3 |

| Segment | Customers | Customer percentage | Net historical value (GBP) |
|---|---:|---:|---:|
| Hibernating | 1,644 | 27.968697% | 667,018.302 |
| Potential Loyalists | 1,412 | 24.021776% | 1,238,541.524 |
| Champions | 1,271 | 21.623001% | 11,620,155.085 |
| At Risk | 708 | 12.044913% | 1,342,516.002 |
| Loyal | 606 | 10.309629% | 1,761,216.025 |
| New Customers | 237 | 4.031984% | 79,896.37 |

Every one of the 5,878 RFM customers appears exactly once. Segments are project-specific descriptive rules, not true personas or churn predictions.

## Observed purchase cohorts

**25 cohorts**, **2009-12 through 2011-12**, and **325 observed cohort/month cells**. Cohort sizes sum to 5,878. Every month-zero rate is 100%; all rates lie within 0–100%. Future cells are NULL rather than zero. December 2011 is partial (observation ends December 9).

| First observed month | Cohort size | Offset | Activity month | Active customers | Retention | Partial month |
|---|---:|---:|---|---:|---:|---:|
| 2009-12 | 955 | 0 | 2009-12 | 955 | 100.000000% | 0 |
| 2009-12 | 955 | 1 | 2010-01 | 337 | 35.287958% | 0 |
| 2009-12 | 955 | 3 | 2010-03 | 406 | 42.513089% | 0 |
| 2009-12 | 955 | 6 | 2010-06 | 360 | 37.696335% | 0 |
| 2009-12 | 955 | 12 | 2010-12 | 359 | 37.591623% | 0 |
| 2009-12 | 955 | 24 | 2011-12 | 188 | 19.685864% | 1 |
| 2010-12 | 76 | 0 | 2010-12 | 76 | 100.000000% | 0 |
| 2010-12 | 76 | 1 | 2011-01 | 7 | 9.210526% | 0 |
| 2010-12 | 76 | 3 | 2011-03 | 7 | 9.210526% | 0 |
| 2010-12 | 76 | 6 | 2011-06 | 4 | 5.263158% | 0 |
| 2010-12 | 76 | 12 | 2011-12 | 2 | 2.631579% | 1 |
| 2011-06 | 108 | 0 | 2011-06 | 108 | 100.000000% | 0 |
| 2011-06 | 108 | 1 | 2011-07 | 25 | 23.148148% | 0 |
| 2011-06 | 108 | 3 | 2011-09 | 29 | 26.851852% | 0 |
| 2011-06 | 108 | 6 | 2011-12 | 9 | 8.333333% | 1 |
| 2011-12 | 28 | 0 | 2011-12 | 28 | 100.000000% | 1 |

Customers may have purchased before the extract begins; first observed purchase is not confirmed acquisition. Purchase retention may rise after skipped months. No qualifying repeat purchase observed is not confirmed churn.

## Repeat purchase and intervals

| Metric | Actual result |
|---|---:|
| purchasers | 5,878 |
| one_time_customers | 1,623 |
| repeat_customers | 4,255 |
| repeat_purchase_rate_pct | 72.38856754 |
| interval_count | 31,091 |
| average_interval_days | 51.6866562626 |
| median_interval_days | 24.7430555555 |
| average_first_second_days | 97.5241949014 |
| median_first_second_days | 55.9604166667 |

Intervals use elapsed timestamp days, including same-day orders. General averages/medians weight each consecutive-order gap equally; first-to-second statistics have one observation per repeat purchaser.

## Historical value and concentration

- Median historical net value across all known ledger customers: **GBP 844.60**.
- Return-only customers contribute **GBP -61,050.92**. This explains the difference between full-ledger and purchaser-only net totals.

| Top concentration metric | Measured result |
|---|---:|
| eligible_customers | 5,878 |
| top_customer_count | 588 |
| top_net_value_micros | 10,574,264,847,000 |
| eligible_net_value_micros | 16,709,343,308,000 |
| top_10pct_share_pct | 63.283545332 |

The top group is exactly 588 of 5,878 purchasers, ranked by net value descending then customer ID ascending. Its **63.283545%** share uses purchaser-only net value, not the full ledger denominator. Historical value is not predicted CLV or audited company revenue.

| Country label | Known customers (not additive across countries) | Net transaction value (GBP) |
|---|---:|---:|
| United Kingdom | 5,407 | 13,806,423.027 |
| EIRE | 5 | 578,501.63 |
| Netherlands | 23 | 548,524.95 |

## Actual SQL usage and local timings

The functioning APIs use JOIN, GROUP BY, CASE, CTEs, RANK/ROW_NUMBER/tie windows, LAG, calendar-month recursion, and conditional aggregation for the retention matrix. SQL performs analytical aggregation; result dataframes are not used to aggregate the million-row source.

| API output | Seconds |
|---|---:|
| executive_kpis | 1.736036 |
| rfm_distribution | 3.131164 |
| rfm_customers | 1.174041 |
| rfm_segments | 1.703307 |
| cohort_retention | 3.232196 |
| cohort_matrix | 3.601089 |
| repeat_purchase | 2.356780 |
| frequency_distribution | 1.046976 |
| order_intervals | 1.164451 |
| customer_value | 1.553435 |
| country_value | 0.811940 |
| value_concentration | 1.561066 |

These single local timings include connection/view setup, query execution, and result fetch. No new indexes or performance optimizations were introduced; no before/after or scalability claim is made.

## Independent validation and regressions

The validator independently streamed 824,293 fact rows and reconstructed 36,969 orders and 5,878 purchasers using Python dictionaries and datetime calculations. It checked exact monetary conservation, per-customer values, recency/frequency/monetary inputs, tie scores, segments, 325 cohort cells, calendar offsets, 31,091 nonnegative intervals and their medians, and concentration. Exported CSV tables were checked again against the fact rows. All checks passed.

- **56 tests passed:** all previous 38 tests plus 18 focused retail customer-analytics tests.
- `python -m compileall analytics etl frontend ml backend`: passed.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed.
- Telco ingestion: **7,043** source/stored customers; **11** missing total charges; zero blocking quality findings.
- Real Telco Analytics page AppTest passed and displayed **7,043** customers / **1,869** observed churn cases.
- Existing Streamlit startup and health: **HTTP 200, ok**.
- Existing Streamlit comparison-component deprecation notices remain. No retail UI was added.

## Issues addressed and remaining limits

Avoided line-count inflation of orders, arbitrary splitting of RFM ties, sign reversal of returns, fabricated identities, and zero-filling future cohort periods. One fixture expectation initially overlooked Champions taking precedence over Loyal and was corrected to match the documented rule.

Remaining limitations: first-observed cohorts are left-censored; December 2011 is partial; observation lengths differ by cohort; repeat rate is over the available window, not a fixed-horizon rate; repeated source lines remain in monetary values; returns are not linked to original orders; customer-only analytics excludes anonymous transactions; order IDs are interpreted at customer/invoice grain; RFM scores are relative to this population and may move when the snapshot changes. No causal effects or churn labels are inferred. Export files are not an atomic multi-file snapshot; avoid concurrent ETL/export runs.

Generated outputs remain local and ignored under `data/processed/retail_analytics/`. Source data, SQLite databases and model artifacts are not added to Git. Milestones 1–3 are preserved. Nothing was pushed, merged, published, or deployed. No retail Streamlit dashboards, Customer 360, Power BI, or additional ML were started.
