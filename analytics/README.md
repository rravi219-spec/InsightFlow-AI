# SQL-backed customer analytics

This page documents the **Telco** domain. The independent [Online Retail II customer analytics layer](RETAIL_CUSTOMER_ANALYTICS.md) defines transaction-based RFM, repeat purchase, historical value, and observed purchase-retention cohorts. The datasets are never joined.

This layer turns the public Telco customer snapshot into a reproducible local SQLite database for portfolio analytics.

## Build the database

```bash
python analytics/sqlite_analytics.py
```

The generated database is `data/insightflow_analytics.sqlite3`. Database files remain ignored by Git, so the database is rebuilt from the tracked public CSV rather than committed.

Ingestion is repeatable: `customer_id` is the primary key and ingestion uses an UPSERT. Re-running the command updates an existing customer instead of inserting a duplicate.

## Data-quality checks

Ingestion fails on missing required columns, duplicate/missing customer IDs, invalid churn labels, tenure outside the integer range 0–72, and missing, negative, or non-finite monthly charges. IDs are read as strings to preserve leading zeros.

Blank `TotalCharges` is reported but is not blocking; it is stored as SQL NULL without imputation. The bundled source has 11 such records, all with zero tenure. Nonblank malformed, negative, or non-finite total charges block ingestion.

The database represents the current source snapshot: ingestion removes stored IDs absent from the validated input. Use a separate database for another dataset. Validation happens before database writes; the refresh is transactional. Connections close after each operation.

New databases explicitly require a non-NULL customer primary key. Existing databases keep their original schema; ingestion still rejects missing IDs before writing.

## Local tests

```bash
python -m unittest discover -s tests -v
python -m compileall analytics frontend ml backend
python -m pip check
```

Tests use temporary CSVs and SQLite databases, including invalid inputs, UPSERT updates, primary-key uniqueness, snapshot refresh, and exact SQL aggregates at tenure-band boundaries.

## KPI definitions

- **Customers**: count of customer records in the segment.
- **Observed churn customers**: count of customers whose source `Churn` is Yes (stored as `observed_churn = 1`).
- **Observed churn rate**: customers whose source `Churn` label is Yes divided by total customers in the relevant group, multiplied by 100 for percentage output. Invalid labels block ingestion rather than changing the denominator.
- **Average tenure**: arithmetic mean of tenure in months for customers in the segment.
- **Average monthly charges**: arithmetic mean of `MonthlyCharges` for customers in the segment.

Observed churn is a historical/source outcome in this snapshot. Predicted churn risk is a model probability, shown separately in the individual/comparison ML section. MonthlyCharges is a billed monthly charge attribute, not realized revenue loss.

Overall query means/rates retain full precision; the UI formats rates/tenure to one decimal and charges to two. Segment queries round rates/charges to two decimals and tenure to one. Empty snapshots have zero counts and undefined (NULL) averages/rates; the page displays an empty-state message.

## Queries

`get_overall_customer_summary()` returns SQL customer/churn counts, observed churn percentage, average tenure, and average monthly charges.

`get_customer_segment_summary()` uses SQL `GROUP BY contract` to calculate customer/churn counts, observed churn rate, average tenure, and average monthly charges.

`get_payment_method_summary()` and `get_internet_service_summary()` return SQL customer counts, observed churn percentages, and average monthly charges per category.

`get_tenure_band_summary()` uses SQL `CASE` bands (0–12, 13–24, 25–48, 49–72 months) before aggregating customer/churn counts, observed churn rate, and average monthly charges.

`get_monthly_charges_distribution()` returns SQLite charge/outcome observations for the existing Plotly box plot. Plotly computes its visual distribution; no duplicate pandas KPI aggregation is maintained.

The Analytics page ingests the validated snapshot before querying SQLite. All descriptive KPIs, segment charts, and tables use these functions. Pandas only receives, orders, renames, and formats query results. The full CSV is read separately for individual profiles and ML feature inputs, not aggregate calculations. Database/source failures display an error without falling back to an inconsistent pandas aggregate path. Reports and other pages are outside this milestone.

Page tests use Streamlit AppTest, temporary SQL databases, mocked navigation, and no external services. Model loading and the sidebar image are excluded from those tests; prediction quality and browser navigation are not asserted. Query reconciliation expectations are calculated independently from controlled source records.

The source dataset is a customer snapshot and does not contain a genuine sequence of dated customer events. Cohort retention is therefore intentionally not calculated from this layer.
