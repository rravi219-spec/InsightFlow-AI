PRAGMA foreign_keys = ON;
CREATE TABLE etl_metadata (key TEXT NOT NULL PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE staging_transaction (
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK(source_row >= 2),
    raw_payload TEXT NOT NULL,
    raw_fingerprint TEXT NOT NULL,
    duplicate_source_row INTEGER NOT NULL CHECK(duplicate_source_row IN (0,1)),
    invoice TEXT,
    product_code TEXT,
    description TEXT,
    customer_id TEXT,
    country TEXT,
    invoice_timestamp TEXT,
    quantity INTEGER,
    unit_price_micros INTEGER,
    amount_micros INTEGER,
    is_cancelled INTEGER NOT NULL CHECK(is_cancelled IN (0,1)),
    quality_flags TEXT NOT NULL,
    exclusion_reasons TEXT NOT NULL,
    eligible INTEGER NOT NULL CHECK(eligible IN (0,1)),
    PRIMARY KEY(source_sheet, source_row)
);
CREATE TABLE dim_customer (
    customer_key TEXT NOT NULL PRIMARY KEY
);
CREATE TABLE dim_product (
    product_key TEXT NOT NULL PRIMARY KEY,
    description TEXT
);
CREATE TABLE dim_country (
    country_key TEXT NOT NULL PRIMARY KEY
);
CREATE TABLE dim_date (
    date_key INTEGER NOT NULL PRIMARY KEY,
    calendar_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    day INTEGER NOT NULL CHECK(day BETWEEN 1 AND 31)
);
CREATE TABLE fact_transaction (
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    invoice TEXT NOT NULL,
    product_key TEXT NOT NULL REFERENCES dim_product(product_key),
    customer_key TEXT REFERENCES dim_customer(customer_key),
    country_key TEXT REFERENCES dim_country(country_key),
    date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    invoice_timestamp TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity != 0),
    unit_price_micros INTEGER NOT NULL CHECK(unit_price_micros > 0),
    amount_micros INTEGER NOT NULL CHECK(amount_micros = quantity * unit_price_micros),
    is_cancelled INTEGER NOT NULL CHECK(is_cancelled IN (0,1)),
    PRIMARY KEY(source_sheet, source_row),
    FOREIGN KEY(source_sheet, source_row) REFERENCES staging_transaction(source_sheet, source_row)
);
CREATE INDEX fact_customer_date ON fact_transaction(customer_key, date_key);
CREATE INDEX fact_invoice ON fact_transaction(invoice);
