"""Read-only SQL customer analytics for the independent Online Retail II domain."""
from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sqlite3

import pandas as pd

from etl.retail_config import DATABASE

SQL_DIR = Path(__file__).with_name("retail_sql")


@contextmanager
def connection(db_path=DATABASE):
    conn = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.executescript((SQL_DIR / "base.sql").read_text(encoding="utf-8"))
        yield conn
    finally:
        conn.close()


def _dates(conn, analysis_date=None):
    end, default = conn.execute("SELECT DATE(MAX(invoice_timestamp)), DATE(MAX(invoice_timestamp), '+1 day') FROM fact_transaction").fetchone()
    if analysis_date is not None:
        analysis_date = date.fromisoformat(str(analysis_date)).isoformat()
        if end is not None and analysis_date <= end:
            raise ValueError("Analysis date must follow the complete observation window; this API is not an as-of filter")
    return {"analysis_date": analysis_date or default, "observation_end": end}


def _read(query, db_path=DATABASE, params=None):
    with connection(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_purchase_orders(db_path=DATABASE):
    return _read("SELECT * FROM retail_orders ORDER BY customer_key, order_timestamp, invoice", db_path)


def get_customer_kpis(db_path=DATABASE):
    return _read("""
        WITH behavior AS (
            SELECT COUNT(*) AS known_analytical_customers,
                COALESCE(SUM(frequency),0) AS purchase_invoices,
                COALESCE(SUM(frequency>=2),0) AS repeat_customers,
                COALESCE(SUM(frequency=1),0) AS one_time_customers,
                100.0*SUM(frequency>=2)/NULLIF(COUNT(*),0) AS repeat_purchase_rate_pct,
                AVG(frequency) AS average_purchase_frequency,
                MIN(first_purchase_date) AS first_purchase_date, MAX(last_purchase_date) AS last_purchase_date
            FROM retail_purchasers
        ), value AS (
            SELECT COUNT(*) AS known_ledger_customers, COALESCE(SUM(eligible_lines),0) AS eligible_transaction_lines,
                COALESCE(SUM(gross_purchase_micros),0) AS gross_purchase_micros,
                COALESCE(SUM(return_signed_micros),0) AS return_signed_micros,
                COALESCE(SUM(net_value_micros),0) AS net_value_micros,
                AVG(net_value_micros)/1000000.0 AS average_customer_value_gbp
            FROM retail_ledger
        )
        SELECT *, -return_signed_micros AS return_cancellation_deduction_micros,
            gross_purchase_micros/1000000.0/NULLIF(purchase_invoices,0) AS average_order_value_gbp,
            known_ledger_customers-known_analytical_customers AS return_only_customers,
            (SELECT COUNT(*) FROM fact_transaction WHERE customer_key IS NULL) AS anonymous_lines,
            (SELECT COUNT(*) FROM retail_known_lines WHERE is_purchase=0 AND amount_micros>0) AS positive_cancellation_lines
        FROM behavior CROSS JOIN value
    """, db_path)


def get_customer_value_detail(db_path=DATABASE):
    return _read("""SELECT l.*, COALESCE(p.frequency,0) AS purchase_invoices,
        p.first_purchase_date, p.last_purchase_date,
        ROW_NUMBER() OVER (ORDER BY l.net_value_micros DESC, l.customer_key) AS value_rank
        FROM retail_ledger l LEFT JOIN retail_purchasers p USING(customer_key)
        ORDER BY value_rank""", db_path)


def get_rfm_distribution(db_path=DATABASE):
    """Inspect actual metric ties/ranges before choosing scoring; no fact rows returned."""
    with connection(db_path) as conn:
        dates = _dates(conn)
        return pd.read_sql_query("""WITH metrics AS (
            SELECT 'recency_days' AS metric, CAST(JULIANDAY(:analysis_date)-JULIANDAY(last_purchase_date) AS INTEGER) AS value FROM retail_purchasers
            UNION ALL SELECT 'frequency', frequency FROM retail_purchasers
            UNION ALL SELECT 'monetary_micros', monetary_micros FROM retail_purchasers)
            SELECT metric,value,COUNT(*) AS customers FROM metrics GROUP BY metric,value ORDER BY metric,value""", conn, params=dates)


def get_rfm_customers(db_path=DATABASE, analysis_date=None):
    with connection(db_path) as conn:
        params = _dates(conn, analysis_date)
        result = pd.read_sql_query((SQL_DIR / "rfm.sql").read_text(encoding="utf-8") + " ORDER BY customer_key", conn, params=params)
        result["analysis_date"] = params["analysis_date"]
        return result


def get_rfm_segment_summary(db_path=DATABASE, analysis_date=None):
    with connection(db_path) as conn:
        query = (SQL_DIR / "rfm.sql").read_text(encoding="utf-8")
        return pd.read_sql_query(f"""WITH rfm AS ({query})
            SELECT segment,COUNT(*) AS customers, 100.0*COUNT(*)/SUM(COUNT(*)) OVER () AS customer_pct,
                SUM(frequency) AS purchase_invoices, AVG(frequency) AS average_frequency,
                SUM(monetary_micros) AS gross_purchase_micros, SUM(l.return_signed_micros) AS return_signed_micros,
                SUM(l.net_value_micros) AS net_value_micros,
                SUM(monetary_micros)/1000000.0/SUM(frequency) AS average_order_value_gbp
            FROM rfm JOIN retail_ledger l USING(customer_key) GROUP BY segment ORDER BY customers DESC, segment""",
            conn, params=_dates(conn, analysis_date))


def get_cohort_retention(db_path=DATABASE):
    with connection(db_path) as conn:
        return pd.read_sql_query((SQL_DIR / "cohorts.sql").read_text(encoding="utf-8"), conn, params=_dates(conn))


def get_cohort_retention_matrix(db_path=DATABASE):
    """SQL conditional aggregation; future/unobserved offsets remain NULL, not zero."""
    with connection(db_path) as conn:
        params = _dates(conn)
        span = conn.execute("""SELECT COALESCE((CAST(STRFTIME('%Y',MAX(invoice_timestamp)) AS INTEGER)-CAST(STRFTIME('%Y',MIN(invoice_timestamp)) AS INTEGER))*12
            +CAST(STRFTIME('%m',MAX(invoice_timestamp)) AS INTEGER)-CAST(STRFTIME('%m',MIN(invoice_timestamp)) AS INTEGER),0) FROM fact_transaction""").fetchone()[0]
        columns = ",".join(f"MAX(CASE WHEN month_offset={i} THEN retention_pct END) AS month_{i}" for i in range(span+1))
        query = (SQL_DIR / "cohorts.sql").read_text(encoding="utf-8")
        return pd.read_sql_query(f"WITH retention AS ({query}) SELECT cohort_month,MAX(cohort_size) AS cohort_size,{columns} FROM retention GROUP BY cohort_month ORDER BY cohort_month", conn, params=params)


def get_order_intervals(db_path=DATABASE):
    return _read("SELECT * FROM retail_order_intervals ORDER BY customer_key,order_number", db_path)


def get_repeat_purchase_summary(db_path=DATABASE):
    return _read("""WITH intervals AS (
        SELECT interval_days, order_number,
            ROW_NUMBER() OVER (ORDER BY interval_days) AS rn, COUNT(*) OVER () AS n
        FROM retail_order_intervals WHERE interval_days IS NOT NULL
    ), first_second AS (
        SELECT interval_days, ROW_NUMBER() OVER (ORDER BY interval_days) AS rn, COUNT(*) OVER () AS n
        FROM intervals WHERE order_number=2
    )
    SELECT COUNT(*) AS purchasers, COALESCE(SUM(frequency=1),0) AS one_time_customers,
        COALESCE(SUM(frequency>=2),0) AS repeat_customers,
        100.0*SUM(frequency>=2)/NULLIF(COUNT(*),0) AS repeat_purchase_rate_pct,
        (SELECT COUNT(*) FROM intervals) AS interval_count,
        (SELECT AVG(interval_days) FROM intervals) AS average_interval_days,
        (SELECT AVG(interval_days) FROM intervals WHERE rn IN ((n+1)/2,(n+2)/2)) AS median_interval_days,
        (SELECT AVG(interval_days) FROM first_second) AS average_first_second_days,
        (SELECT AVG(interval_days) FROM first_second WHERE rn IN ((n+1)/2,(n+2)/2)) AS median_first_second_days
    FROM retail_purchasers""", db_path)


def get_purchase_frequency_distribution(db_path=DATABASE):
    return _read("SELECT frequency AS purchase_invoices,COUNT(*) AS customers FROM retail_purchasers GROUP BY frequency ORDER BY frequency", db_path)


def get_country_value_summary(db_path=DATABASE):
    return _read("""SELECT country_key, COUNT(*) AS transaction_lines, COUNT(DISTINCT customer_key) AS known_customers,
        SUM(CASE WHEN is_purchase=1 THEN amount_micros ELSE 0 END) AS gross_purchase_micros,
        SUM(CASE WHEN is_purchase=0 THEN amount_micros ELSE 0 END) AS return_signed_micros,
        SUM(amount_micros) AS net_value_micros FROM retail_known_lines GROUP BY country_key ORDER BY net_value_micros DESC""", db_path)


def get_customer_value_concentration(db_path=DATABASE):
    return _read("""WITH ranked AS (
        SELECT l.customer_key,l.net_value_micros,
            ROW_NUMBER() OVER (ORDER BY l.net_value_micros DESC,l.customer_key) AS rn,
            COUNT(*) OVER () AS n
        FROM retail_ledger l JOIN retail_purchasers p USING(customer_key)
    )
    SELECT COUNT(*) AS eligible_customers, COALESCE(MAX((n+9)/10),0) AS top_customer_count,
        COALESCE(SUM(CASE WHEN rn <= (n+9)/10 THEN net_value_micros ELSE 0 END),0) AS top_net_value_micros,
        COALESCE(SUM(net_value_micros),0) AS eligible_net_value_micros,
        CASE WHEN SUM(net_value_micros)>0 THEN 100.0*SUM(CASE WHEN rn <= (n+9)/10 THEN net_value_micros ELSE 0 END)/SUM(net_value_micros) END AS top_10pct_share_pct
    FROM ranked""", db_path)
