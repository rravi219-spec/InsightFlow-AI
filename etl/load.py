"""SQLite persistence; dimensions use actual business keys, not invented attributes."""
from pathlib import Path


def initialize(conn):
    conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO etl_metadata VALUES ('pipeline', 'insightflow_retail_v1')")


def load_batch(conn, records):
    conn.executemany("INSERT INTO staging_transaction VALUES (" + ",".join(["?"] * 18) + ")", records)


def populate_analytics(conn):
    conn.execute("""INSERT INTO dim_customer
        SELECT DISTINCT customer_id FROM staging_transaction
        WHERE eligible=1 AND customer_id IS NOT NULL""")
    conn.execute("""INSERT INTO dim_country
        SELECT DISTINCT country FROM staging_transaction
        WHERE eligible=1 AND country IS NOT NULL""")
    # A deterministic representative description only; all original descriptions remain in staging.
    conn.execute("""INSERT INTO dim_product
        SELECT product_code, MIN(description) FROM staging_transaction
        WHERE eligible=1 GROUP BY product_code""")
    conn.execute("""INSERT INTO dim_date
        SELECT DISTINCT CAST(REPLACE(SUBSTR(invoice_timestamp,1,10),'-','') AS INTEGER),
            SUBSTR(invoice_timestamp,1,10), CAST(SUBSTR(invoice_timestamp,1,4) AS INTEGER),
            CAST(SUBSTR(invoice_timestamp,6,2) AS INTEGER), CAST(SUBSTR(invoice_timestamp,9,2) AS INTEGER)
        FROM staging_transaction WHERE eligible=1""")
    conn.execute("""INSERT INTO fact_transaction
        SELECT source_sheet,source_row,invoice,product_code,customer_id,country,
            CAST(REPLACE(SUBSTR(invoice_timestamp,1,10),'-','') AS INTEGER),
            invoice_timestamp,quantity,unit_price_micros,amount_micros,is_cancelled
        FROM staging_transaction WHERE eligible=1""")
