"""Fail the build before publication if source accounting or relational checks fail."""

TABLES = ("staging_transaction", "fact_transaction", "dim_customer", "dim_product", "dim_date", "dim_country")


def require(condition, message):
    if not condition:
        raise ValueError(f"Reconciliation failed: {message}")


def reconcile(conn, expected):
    counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES}
    require(counts["staging_transaction"] == expected["raw_rows"], "source/staging accounting")
    require(counts["fact_transaction"] == expected["valid_analytical_rows"], "eligible/fact accounting")
    excluded = conn.execute("SELECT COUNT(*) FROM staging_transaction WHERE eligible=0").fetchone()[0]
    require(counts["fact_transaction"] + excluded == counts["staging_transaction"], "source/fact/excluded accounting")
    require(not conn.execute("PRAGMA foreign_key_check").fetchall(), "foreign keys")
    require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity")
    mismatches = conn.execute("""SELECT COUNT(*) FROM staging_transaction s
        LEFT JOIN fact_transaction f USING(source_sheet,source_row)
        WHERE (s.eligible=1 AND (f.source_row IS NULL
            OR f.invoice IS NOT s.invoice OR f.product_key IS NOT s.product_code
            OR f.customer_key IS NOT s.customer_id OR f.country_key IS NOT s.country
            OR f.invoice_timestamp IS NOT s.invoice_timestamp OR f.quantity IS NOT s.quantity
            OR f.unit_price_micros IS NOT s.unit_price_micros OR f.amount_micros IS NOT s.amount_micros
            OR f.is_cancelled IS NOT s.is_cancelled))
            OR (s.eligible=0 AND f.source_row IS NOT NULL)""").fetchone()[0]
    require(mismatches == 0, "row-level staging/fact agreement")
    date_mismatches = conn.execute("""SELECT COUNT(*) FROM fact_transaction f
        JOIN dim_date d USING(date_key)
        WHERE SUBSTR(f.invoice_timestamp,1,10) != d.calendar_date""").fetchone()[0]
    require(date_mismatches == 0, "fact timestamp/date dimension agreement")
    require(conn.execute("SELECT COUNT(*) FROM fact_transaction WHERE amount_micros != quantity * unit_price_micros").fetchone()[0] == 0,
            "amount arithmetic")
    for table, key in [("dim_customer", "customer_key"), ("dim_product", "product_key"),
                       ("dim_country", "country_key"), ("dim_date", "date_key")]:
        n = conn.execute(f"SELECT COUNT(DISTINCT {key}) FROM {table}").fetchone()[0]
        fact_n = conn.execute(f"SELECT COUNT(DISTINCT {key}) FROM fact_transaction").fetchone()[0]
        require(n == counts[table] == fact_n, f"{table} unique and used keys")
    distinct = conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT source_sheet,source_row FROM fact_transaction)").fetchone()[0]
    require(distinct == counts["fact_transaction"], "fact primary key uniqueness")
    aggregate = conn.execute("""SELECT COALESCE(SUM(amount_micros),0), MIN(invoice_timestamp), MAX(invoice_timestamp),
        COUNT(DISTINCT invoice), COUNT(DISTINCT customer_key), SUM(customer_key IS NULL)
        FROM fact_transaction""").fetchone()
    actual = dict(zip(("amount_micros", "date_min", "date_max", "invoices", "customers", "anonymous_rows"), aggregate))
    actual["anonymous_rows"] = actual["anonymous_rows"] or 0
    require(actual == expected["analytical_totals"], f"transformed stream totals: {actual}")
    return {"status": "passed", "counts": counts, "excluded_rows": excluded,
            "analytical_totals": actual, "foreign_key_violations": 0, "row_mismatches": mismatches}
