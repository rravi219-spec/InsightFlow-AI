from __future__ import annotations

from typing import Any

import pandas as pd


COLUMN_PATTERNS = {
    "customer_id": [
        "customerid",
        "customer_id",
        "clientid",
        "client_id",
        "accountid",
        "account_id",
        "name",
    ],
    "usage": [
        "usage",
        "productusage",
        "product_usage",
        "logins",
        "sessions",
        "activity",
    ],
    "tickets": [
        "tickets",
        "supporttickets",
        "support_tickets",
        "cases",
        "complaints",
    ],
    "nps": [
        "nps",
        "satisfaction",
        "customer_satisfaction",
        "csat",
    ],
    "revenue": [
        "revenue",
        "monthlycharges",
        "monthly_charges",
        "totalcharges",
        "total_charges",
        "arr",
        "mrr",
    ],
    "tenure": [
        "tenure",
        "customer_age",
        "months_active",
        "subscription_length",
    ],
    "churn": [
        "churn",
        "churned",
        "is_churned",
        "cancelled",
        "canceled",
    ],
    "contract": [
        "contract",
        "contract_type",
        "plan",
        "subscription",
    ],
}


def normalize_column_name(column: str) -> str:
    return (
        column.strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


def detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    normalized_columns = {
        normalize_column_name(column): column
        for column in df.columns
    }

    detected: dict[str, str | None] = {}

    for role, patterns in COLUMN_PATTERNS.items():
        detected[role] = None

        normalized_patterns = {
            normalize_column_name(pattern)
            for pattern in patterns
        }

        for normalized_name, original_name in normalized_columns.items():
            if normalized_name in normalized_patterns:
                detected[role] = original_name
                break

    return detected


def summarize_dataset(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "numeric_columns": df.select_dtypes(
            include="number"
        ).columns.tolist(),
        "categorical_columns": df.select_dtypes(
            exclude="number"
        ).columns.tolist(),
    }