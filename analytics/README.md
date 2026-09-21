# SQL-backed customer analytics

This layer turns the public Telco customer snapshot into a reproducible local SQLite database for portfolio analytics.

## Build the database

```bash
python analytics/sqlite_analytics.py
```

The generated database is `data/insightflow_analytics.sqlite3`. Database files remain ignored by Git, so the database is rebuilt from the tracked public CSV rather than committed.

Ingestion is repeatable: `customer_id` is the primary key and ingestion uses an UPSERT. Re-running the command updates an existing customer instead of inserting a duplicate.

## Data-quality checks

Ingestion fails on duplicate/missing customer IDs, invalid churn labels, negative/missing tenure, and negative/missing monthly charges. Missing `TotalCharges` is reported but is not blocking because the source can contain blank total charges for customers with little or no tenure.

## KPI definitions

- **Customers**: count of customer records in the segment.
- **Observed churn rate**: customers whose source `Churn` label is Yes divided by customers in the segment with a valid ingested label.
- **Average tenure**: arithmetic mean of tenure in months for customers in the segment.
- **Average monthly charges**: arithmetic mean of `MonthlyCharges` for customers in the segment.

Observed churn is a historical label in this snapshot. It is not the model's predicted churn probability and it is not a realized revenue-loss measure.

## Queries

`get_customer_segment_summary()` uses SQL `GROUP BY contract` to calculate customer counts, observed churn rate, average tenure, and average monthly charges.

`get_tenure_band_summary()` uses a SQL `CASE` expression to create lifecycle bands before aggregating customer count, observed churn rate, and average monthly charges.

The source dataset is a customer snapshot and does not contain a genuine sequence of dated customer events. Cohort retention is therefore intentionally not calculated from this layer.
