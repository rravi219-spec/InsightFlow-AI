from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
DB_PATH = PROJECT_ROOT / "data" / "insightflow_analytics.sqlite3"

REQUIRED_COLUMNS = {
    "customerID",
    "tenure",
    "Contract",
    "PaymentMethod",
    "InternetService",
    "MonthlyCharges",
    "TotalCharges",
    "Churn",
}

CREATE_CUSTOMERS_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    tenure INTEGER,
    contract TEXT,
    payment_method TEXT,
    internet_service TEXT,
    monthly_charges REAL,
    total_charges REAL,
    observed_churn INTEGER NOT NULL CHECK (observed_churn IN (0, 1))
)
"""


def load_source_dataframe(csv_path: Path = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    cleaned = df.copy()
    cleaned["customerID"] = cleaned["customerID"].astype("string").str.strip()
    cleaned["tenure"] = pd.to_numeric(cleaned["tenure"], errors="coerce")
    cleaned["MonthlyCharges"] = pd.to_numeric(
        cleaned["MonthlyCharges"], errors="coerce"
    )
    cleaned["TotalCharges"] = pd.to_numeric(
        cleaned["TotalCharges"], errors="coerce"
    )
    cleaned["observed_churn"] = (
        cleaned["Churn"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"yes": 1, "no": 0})
    )

    return cleaned


def run_data_quality_checks(df: pd.DataFrame) -> dict[str, int]:
    invalid_churn = int(df["observed_churn"].isna().sum())
    duplicate_customer_ids = int(df["customerID"].duplicated().sum())
    missing_customer_ids = int(
        (df["customerID"].isna() | df["customerID"].eq("")).sum()
    )
    invalid_tenure = int(
        ((df["tenure"].isna()) | (df["tenure"] < 0) | (df["tenure"] > 72)).sum()
    )
    invalid_monthly_charges = int(
        ((df["MonthlyCharges"].isna()) | (df["MonthlyCharges"] < 0)).sum()
    )

    return {
        "rows": int(len(df)),
        "duplicate_customer_ids": duplicate_customer_ids,
        "missing_customer_ids": missing_customer_ids,
        "invalid_churn_labels": invalid_churn,
        "invalid_tenure_values": invalid_tenure,
        "invalid_monthly_charges": invalid_monthly_charges,
        "missing_total_charges": int(df["TotalCharges"].isna().sum()),
    }


def validate_for_ingestion(df: pd.DataFrame) -> dict[str, int]:
    checks = run_data_quality_checks(df)
    blocking = {
        "duplicate_customer_ids": checks["duplicate_customer_ids"],
        "missing_customer_ids": checks["missing_customer_ids"],
        "invalid_churn_labels": checks["invalid_churn_labels"],
        "invalid_tenure_values": checks["invalid_tenure_values"],
        "invalid_monthly_charges": checks["invalid_monthly_charges"],
    }

    failures = {key: value for key, value in blocking.items() if value > 0}
    if failures:
        raise ValueError(f"Data quality checks failed: {failures}")

    return checks


def prepare_customer_rows(df: pd.DataFrame) -> list[tuple]:
    return list(
        df[
            [
                "customerID",
                "tenure",
                "Contract",
                "PaymentMethod",
                "InternetService",
                "MonthlyCharges",
                "TotalCharges",
                "observed_churn",
            ]
        ]
        .itertuples(index=False, name=None)
    )


def ingest_customers(
    csv_path: Path = DATA_PATH,
    db_path: Path = DB_PATH,
) -> dict[str, int]:
    df = load_source_dataframe(csv_path)
    checks = validate_for_ingestion(df)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_CUSTOMERS_SQL)
        source_ids = set(df["customerID"].astype(str))
        stored_ids = {
            row[0]
            for row in conn.execute("SELECT customer_id FROM customers").fetchall()
        }
        stale_ids = stored_ids - source_ids
        if stale_ids:
            conn.executemany(
                "DELETE FROM customers WHERE customer_id = ?",
                [(customer_id,) for customer_id in stale_ids],
            )

        conn.executemany(
            """
            INSERT INTO customers (
                customer_id,
                tenure,
                contract,
                payment_method,
                internet_service,
                monthly_charges,
                total_charges,
                observed_churn
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
                tenure = excluded.tenure,
                contract = excluded.contract,
                payment_method = excluded.payment_method,
                internet_service = excluded.internet_service,
                monthly_charges = excluded.monthly_charges,
                total_charges = excluded.total_charges,
                observed_churn = excluded.observed_churn
            """,
            prepare_customer_rows(df),
        )
        conn.commit()
        stored_rows = conn.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]

    return {
        **checks,
        "stored_rows": int(stored_rows),
    }


def get_customer_segment_summary(
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    query = """
    SELECT
        contract,
        COUNT(*) AS customers,
        ROUND(100.0 * AVG(observed_churn), 2) AS observed_churn_rate_pct,
        ROUND(AVG(tenure), 1) AS avg_tenure_months,
        ROUND(AVG(monthly_charges), 2) AS avg_monthly_charges
    FROM customers
    GROUP BY contract
    ORDER BY observed_churn_rate_pct DESC, customers DESC
    """

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn)


def get_tenure_band_summary(
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    query = """
    WITH tenure_bands AS (
        SELECT
            CASE
                WHEN tenure <= 12 THEN '0-12 months'
                WHEN tenure <= 24 THEN '13-24 months'
                WHEN tenure <= 48 THEN '25-48 months'
                ELSE '49+ months'
            END AS tenure_band,
            CASE
                WHEN tenure <= 12 THEN 1
                WHEN tenure <= 24 THEN 2
                WHEN tenure <= 48 THEN 3
                ELSE 4
            END AS band_order,
            observed_churn,
            monthly_charges
        FROM customers
    )
    SELECT
        tenure_band,
        COUNT(*) AS customers,
        ROUND(100.0 * AVG(observed_churn), 2) AS observed_churn_rate_pct,
        ROUND(AVG(monthly_charges), 2) AS avg_monthly_charges
    FROM tenure_bands
    GROUP BY tenure_band, band_order
    ORDER BY band_order
    """

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn)


if __name__ == "__main__":
    result = ingest_customers()
    print("InsightFlow analytics database is ready.")
    for key, value in result.items():
        print(f"{key}: {value}")
