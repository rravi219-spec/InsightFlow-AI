# Retail customer analytics: definitions and API

This layer reads the separate Online Retail II dimensional database. It does not alter the ETL, join retail customers to Telco, predict churn/CLV, or add dashboards. All aggregation runs in SQLite. Python returns result tables, exports them, and independently validates them.

## Eligibility and populations

1. **Fact population:** Milestone 3's eligible positive-price transaction lines. Zero-price records, negative-price records, invalid core fields, and unsupported invoice formats remain excluded in staging under the existing ETL rules. This layer does not recover or silently refilter them.
2. **Known ledger population:** fact rows with a real customer key, joined to `dim_customer` and `dim_date`. All signed return/cancellation lines remain. Anonymous lines are counted separately, never assigned invented identities, and excluded from customer metrics.
3. **Qualifying purchase:** a known ledger line with `quantity > 0` and `is_cancelled = 0`. A positive-quantity C-prefixed cancellation is not a purchase. A negative non-C adjustment is not a purchase.
4. **Behavioral / RFM population:** known customers with at least one qualifying purchase. Customers with only returns/cancellations remain in the known value ledger, but have no invented purchase date, RFM score, or cohort.

Duplicate source occurrences stay retained, consistent with the ETL. They can increase line values, but multiple lines of a customer/invoice pair count as one order. **Order grain = `(customer_key, invoice)` across the workbook**, with timestamp equal to the earliest qualifying line timestamp. Different invoices on the same day are distinct orders; intervals may be zero or fractional days. No return-to-original-order matching is inferred.

## KPI dictionary

All values are historical, limited to the workbook observation window. Amount sums remain exact integer GBP millionths (`*_micros`). GBP presentation divides by 1,000,000; averages use floating-point division. Monetary source precision can exceed two decimal places, so exports keep the exact integer totals.

| Output | Definition / denominator |
|---|---|
| `known_analytical_customers` | Distinct known customers with >=1 qualifying purchase |
| `known_ledger_customers` | Distinct known customers across all eligible fact lines, including return-only customers |
| `eligible_transaction_lines` | Count of known-customer fact rows; a line count, not an order count |
| `anonymous_lines` | Fact rows with NULL customer key, reported separately |
| `purchase_invoices` | Count of distinct customer/invoice purchase pairs |
| `one_time_customers` | Behavioral customers with exactly one purchase invoice |
| `repeat_customers` | Behavioral customers with >=2 purchase invoices |
| `repeat_purchase_rate_pct` | Repeat customers / all behavioral customers ×100 |
| `gross_purchase_micros` | Sum of qualifying purchase line amounts |
| `return_signed_micros` | Sum of every other known ledger line's source-signed amount, including anomalous positive cancellation amounts |
| `return_cancellation_deduction_micros` | Negative of signed adjustment total; a net deduction, not an absolute-value sum |
| `net_value_micros` | Gross purchases + signed return/cancellation adjustments across all known ledger customers |
| `average_order_value_gbp` | Gross qualifying purchase value / purchase invoices; returns are not retroactively allocated to orders |
| `average_purchase_frequency` | Purchase invoices / behavioral customers |
| `average_customer_value_gbp` | Net known-ledger value / known ledger customers, including return-only customers |
| First / last purchase date | Earliest / latest qualifying order calendar date, per customer or overall as labeled |

Empty denominators produce NULL/undefined averages and percentages rather than invented zeros. Counts and value sums are zero for an empty population.

## RFM scoring

Default reference date = **one calendar day after the latest fact timestamp's date**, including anonymous/return rows when finding the observation end. It is reproducible, independent of today's date. Callers may pass a later ISO reference date, but dates inside/before the completed observation window are rejected: this API is not a historical as-of filter.

- **R:** calendar days between reference date and last qualifying purchase date. Lower is better.
- **F:** distinct customer/invoice qualifying purchase count. Higher is better.
- **M:** gross qualifying purchase amount, not net value after returns. Higher is better. Net historical value is available separately.

Use `get_rfm_distribution()` to inspect actual frequencies, metric ranges, and ties. Equal values must not be split arbitrarily. For each metric, order from worst to best, obtain the 1-based starting rank `r` and tie count `t`, then compute:

```text
midpoint_percentile = (r - 1 + (t - 1)/2) / (N - 1)
score = min(5, 1 + floor(5 * midpoint_percentile))
```

A singleton receives score 3. An all-equal population also receives score 3. Recency sorts descending; frequency and monetary sort ascending. This is a tie-aware percentile scoring rule, not equal-sized quintile allocation. Score bands may have unequal sizes or be empty.

The following CASE rules run in this exact precedence order; the first match wins:

| Segment | Rule |
|---|---|
| Champions | R >=4, F >=4, M >=4 |
| Loyal | R >=3, F >=4 |
| New Customers | R >=4 and exactly one purchase invoice |
| Potential Loyalists | R >=3 |
| At Risk | F >=3 (after the higher-recency cases above) |
| Hibernating | All remaining purchasers |

These are project-specific analytical rules, not universal industry definitions or ground-truth personas. “New” means a recently observed one-time purchaser within this dataset, not confirmed business acquisition. “At Risk” is a descriptive RFM label, not a churn probability.

Segment counts/percentages use the behavioral population. Segment gross/AOV uses purchases. Segment net values include adjustments for those purchasers; return-only customers are absent, so segment net totals differ from the full known ledger by the separately identifiable return-only ledger value.

## Cohorts and retention

Each known purchaser is assigned to the calendar month of their **first observed qualifying purchase**. Dataset entry does not prove true acquisition: customers may have bought before the extract starts (left censoring).

```text
month offset = 12 × (activity year - cohort year) + activity month - cohort month
retention = distinct cohort customers purchasing in activity month / original cohort size
```

The recursive calendar grid generates equivalent offsets across year boundaries. Multiple orders/lines within a month count once per customer. Returns do not create activity. Month zero is 100%. Observed months with no qualifying purchases are zero; future/unobserved cells are NULL in the wide matrix. The final month is marked `is_partial_month` if the observation end is before month-end; it must not be compared uncritically with complete months. The long table carries that flag; matrix consumers should retain the observation-end metadata/long-table flag alongside the matrix.

This is purchase activity retention, not continuous subscription retention or survival probability. Rates may rise after a customer skips a month. No qualifying repeat purchase observed does **not** mean confirmed churn.

## Repeat purchase and value

`LAG` calculates elapsed days between consecutive order timestamps, ordered by timestamp then invoice for deterministic ties. First-to-second intervals have one observation per repeat purchaser. General interval mean/median has one observation per consecutive-order gap and therefore gives frequent purchasers more observations. Median is calculated in SQL using ranked middle values, including the average of two middle values for even samples.

Customer detail includes every known ledger customer's net/gross/adjustment values, purchase count, and dates. Country value uses the transaction's country, not an invented static customer country. Country customer counts can overlap and must not be summed as a global distinct-customer count. Country monetary totals reconcile to the known ledger.

Top-10% concentration ranks **behavioral customers** by net historical value descending and customer key ascending to break ties deterministically. It selects exactly `ceil(N/10)` customers (no expansion for monetary ties). The numerator is those customers' signed net value; denominator is the signed net value of all behavioral customers. Return-only customers are outside this denominator. The percentage is undefined if the denominator is nonpositive. With negative-valued customers, a signed-net concentration percentage can exceed 100%; it is not a bounded market-share measure.

Historical customer value is **not predicted CLV**. Transaction value is **not audited company revenue**. Retention is **not churn**. Associations between country, segment, frequency, and value do not establish causes or intervention outcomes.

## Reusable API and outputs

```python
from analytics.retail_customer_analytics import (
    get_customer_kpis, get_rfm_customers, get_rfm_segment_summary,
    get_cohort_retention, get_cohort_retention_matrix,
    get_repeat_purchase_summary, get_purchase_frequency_distribution,
    get_customer_value_detail, get_country_value_summary,
    get_customer_value_concentration, get_purchase_orders, get_order_intervals,
)
kpis = get_customer_kpis()                 # one-row dataframe
rfm = get_rfm_customers()                  # customer-level detail
retention = get_cohort_retention()         # counts, denominators, flags, percentages
```

Every function accepts a database path for isolated fixture testing. Connections open the database in read-only mode. Temporary SQL views are connection-local and do not alter the dimensional model. No persistent indexes or tables are introduced by analytics.

```powershell
.venv\Scripts\python.exe -m analytics.run_retail_analytics
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall analytics etl frontend ml backend
.venv\Scripts\python.exe -m pip check
```

The runner exports clean CSV tables and `validation.json` to ignored `data/processed/retail_analytics/`. It accepts `--database` and `--output-dir`. Files are written after validation, but the output directory is not an atomic multi-file snapshot; run one export at a time and avoid concurrent ETL replacement. Timings include opening the connection, initializing temporary views, executing SQL, and fetching the result; they exclude CSV writing and independent validation. They are single local measurements, not scalability guarantees.

## SQL and validation

The [base SQL](retail_sql/base.sql) uses dimension JOINs, conditional purchase classification, and GROUP BY at order/customer grain. [RFM SQL](retail_sql/rfm.sql) uses CTEs, window ranks/tie counts, and CASE precedence. [Cohort SQL](retail_sql/cohorts.sql) uses recursive calendar-month aggregation. The matrix API uses conditional aggregation; interval analysis uses LAG and ROW_NUMBER; customer concentration uses deterministic ranking.

`retail_validation.py` independently streams fact rows using Python dictionaries and datetime arithmetic. It checks customer/order counts, gross/adjustment/net values, per-customer RFM inputs and tie scores, segment coverage, cohort membership/activity/grid/denominators, repeat counts, intervals/medians, per-customer value, and top-customer value. It never loads the million-row source into pandas. Synthetic workbook tests include multi-line orders, duplicate occurrences, anonymous customers, signed and positive cancellations, zero-price exclusions, return-only customers, same-day purchases, year boundaries, missing observation cells, and empty/tied populations.

See [measured Milestone 4 results](RETAIL_CUSTOMER_VALIDATION.md) for actual outputs, checks, and query timings.
