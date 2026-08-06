from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Adaptive Customer Analytics",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Adaptive Customer Analytics Dashboard")
st.caption(
    "Upload a CSV or Excel file. The dashboard automatically "
    "profiles the dataset and generates relevant analysis."
)


ROLE_ALIASES = {
    "customer_id": [
        "customerid",
        "customer_id",
        "clientid",
        "client_id",
        "accountid",
        "account_id",
        "customer",
        "name",
    ],
    "revenue": [
        "revenue",
        "monthlycharges",
        "monthly_charges",
        "totalcharges",
        "total_charges",
        "mrr",
        "arr",
        "sales",
        "amount",
    ],
    "tenure": [
        "tenure",
        "monthsactive",
        "months_active",
        "customerage",
        "customer_age",
        "subscriptionlength",
    ],
    "churn": [
        "churn",
        "churned",
        "cancelled",
        "canceled",
        "attrition",
        "left",
        "exited",
    ],
    "contract": [
        "contract",
        "contracttype",
        "contract_type",
        "plan",
        "subscription",
        "package",
    ],
    "usage": [
        "usage",
        "productusage",
        "product_usage",
        "activity",
        "sessions",
        "logins",
        "engagement",
    ],
    "tickets": [
        "tickets",
        "supporttickets",
        "support_tickets",
        "cases",
        "complaints",
        "issues",
    ],
    "satisfaction": [
        "nps",
        "csat",
        "satisfaction",
        "customersatisfaction",
        "customer_satisfaction",
        "rating",
    ],
}


def normalize_name(value: str) -> str:
    """Normalize column names for comparison."""

    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Perform safe, general-purpose cleaning."""

    cleaned = df.copy()

    cleaned.columns = [
        str(column).strip()
        for column in cleaned.columns
    ]

    # Convert object columns to numbers when most values are numeric.
    for column in cleaned.select_dtypes(include="object").columns:
        converted = pd.to_numeric(
            cleaned[column].astype(str).str.strip(),
            errors="coerce",
        )

        valid_ratio = converted.notna().mean()

        if valid_ratio >= 0.80:
            cleaned[column] = converted
        else:
            cleaned[column] = (
                cleaned[column]
                .astype(str)
                .str.strip()
            )

    return cleaned


def detect_column(
    df: pd.DataFrame,
    role: str,
) -> Optional[str]:
    """Find the most likely column for a business role."""

    aliases = {
        normalize_name(alias)
        for alias in ROLE_ALIASES[role]
    }

    for column in df.columns:
        if normalize_name(column) in aliases:
            return column

    # Secondary partial-match check.
    for column in df.columns:
        normalized_column = normalize_name(column)

        if any(
            alias in normalized_column
            or normalized_column in alias
            for alias in aliases
        ):
            return column

    return None


def mapping_index(
    options: list[str],
    detected: Optional[str],
) -> int:
    """Return the dropdown index for an automatically detected field."""

    if detected and detected in options:
        return options.index(detected)

    return 0


def calculate_positive_rate(series: pd.Series) -> float:
    """Estimate the positive/churn percentage from common label formats."""

    normalized = (
        series.astype(str)
        .str.strip()
        .str.lower()
    )

    positive_labels = {
        "yes",
        "true",
        "1",
        "churned",
        "cancelled",
        "canceled",
        "left",
        "exited",
    }

    return normalized.isin(positive_labels).mean() * 100


uploaded_file = st.sidebar.file_uploader(
    "Upload CSV or Excel file",
    type=["csv", "xlsx", "xls"],
)


if uploaded_file is None:
    st.info(
        "Upload a CSV or Excel file from the sidebar to begin."
    )
    st.stop()


try:
    if uploaded_file.name.lower().endswith(".csv"):
        raw_df = pd.read_csv(uploaded_file)
    else:
        raw_df = pd.read_excel(uploaded_file)

except Exception as error:
    st.error(f"Could not read the uploaded file: {error}")
    st.stop()


# =====================================================
# DATA PREPARATION
# =====================================================

df = clean_dataframe(raw_df)

if df.empty:
    st.warning("The uploaded dataset is empty.")
    st.stop()


# =====================================================
# AUTOMATIC COLUMN DETECTION
# =====================================================

numeric_columns = df.select_dtypes(include="number").columns.tolist()

categorical_columns = df.select_dtypes(exclude="number").columns.tolist()


detected = {
    role: detect_column(df, role)
    for role in ROLE_ALIASES
}


df = clean_dataframe(raw_df)

if df.empty:
    st.warning("The uploaded file contains no rows.")
    st.stop()


# Automatic detection
detected = {
    role: detect_column(df, role)
    for role in ROLE_ALIASES
}


# User-confirmed mappings
st.sidebar.header("Column Mapping")

column_options = ["None"] + df.columns.tolist()

mappings = {}

for role in ROLE_ALIASES:
    automatically_detected = detected[role]

    mappings[role] = st.sidebar.selectbox(
        role.replace("_", " ").title(),
        options=column_options,
        index=mapping_index(
            column_options,
            automatically_detected,
        ),
        help=(
            f"Automatically detected: "
            f"{automatically_detected or 'None'}"
        ),
    )

    if mappings[role] == "None":
        mappings[role] = None


# Dataset overview
st.subheader("Dataset Overview")

overview1, overview2, overview3, overview4 = st.columns(4)

overview1.metric("Rows", f"{len(df):,}")
overview2.metric("Columns", len(df.columns))
overview3.metric(
    "Missing Values",
    f"{int(df.isna().sum().sum()):,}",
)
overview4.metric(
    "Duplicate Rows",
    f"{int(df.duplicated().sum()):,}",
)


# Dynamic business KPIs
st.subheader("Business KPIs")

kpis: list[tuple[str, str]] = []

customer_column = mappings["customer_id"]

if customer_column:
    unique_customers = df[customer_column].nunique()
    kpis.append(("Customers", f"{unique_customers:,}"))
else:
    kpis.append(("Records", f"{len(df):,}"))


revenue_column = mappings["revenue"]

if revenue_column:
    revenue_values = pd.to_numeric(
        df[revenue_column],
        errors="coerce",
    )

    kpis.append(
        (
            f"Average {revenue_column}",
            f"{revenue_values.mean():,.2f}",
        )
    )


tenure_column = mappings["tenure"]

if tenure_column:
    tenure_values = pd.to_numeric(
        df[tenure_column],
        errors="coerce",
    )

    kpis.append(
        (
            f"Average {tenure_column}",
            f"{tenure_values.mean():,.1f}",
        )
    )


churn_column = mappings["churn"]

if churn_column:
    churn_rate = calculate_positive_rate(
        df[churn_column]
    )

    kpis.append(
        ("Positive/Churn Rate", f"{churn_rate:.1f}%")
    )


usage_column = mappings["usage"]

if usage_column:
    usage_values = pd.to_numeric(
        df[usage_column],
        errors="coerce",
    )

    kpis.append(
        (
            f"Average {usage_column}",
            f"{usage_values.mean():,.1f}",
        )
    )


ticket_column = mappings["tickets"]

if ticket_column:
    ticket_values = pd.to_numeric(
        df[ticket_column],
        errors="coerce",
    )

    kpis.append(
        (
            f"Total {ticket_column}",
            f"{ticket_values.sum():,.0f}",
        )
    )


for start in range(0, len(kpis), 4):
    row_items = kpis[start:start + 4]
    columns = st.columns(len(row_items))

    for container, (label, value) in zip(
        columns,
        row_items,
    ):
        container.metric(label, value)


st.divider()


# Search
filtered_df = df.copy()

if customer_column:
    search_value = st.text_input(
        "Search customer",
        placeholder=(
            f"Search using {customer_column}"
        ),
    )

    if search_value:
        filtered_df = filtered_df[
            filtered_df[customer_column]
            .astype(str)
            .str.contains(
                search_value,
                case=False,
                na=False,
            )
        ]


# Dataset preview
st.subheader("Dataset Preview")

st.dataframe(
    filtered_df.head(1_000),
    use_container_width=True,
    hide_index=True,
)

if len(filtered_df) > 1_000:
    st.caption(
        "Showing the first 1,000 rows for performance."
    )


# Column profiling
st.subheader("Column Profile")

profile = pd.DataFrame(
    {
        "Column": df.columns,
        "Data Type": [
            str(df[column].dtype)
            for column in df.columns
        ],
        "Missing": [
            int(df[column].isna().sum())
            for column in df.columns
        ],
        "Unique Values": [
            int(df[column].nunique(dropna=True))
            for column in df.columns
        ],
    }
)

st.dataframe(
    profile,
    use_container_width=True,
    hide_index=True,
)


numeric_columns = (
    filtered_df.select_dtypes(include="number")
    .columns
    .tolist()
)

categorical_columns = (
    filtered_df.select_dtypes(exclude="number")
    .columns
    .tolist()
)


# Generic numeric chart
if numeric_columns:
    st.subheader("Numeric Analysis")

    selected_numeric = st.selectbox(
        "Choose a numeric column",
        options=numeric_columns,
    )

    numeric_chart = px.histogram(
        filtered_df,
        x=selected_numeric,
        nbins=30,
        title=f"Distribution of {selected_numeric}",
    )

    st.plotly_chart(
        numeric_chart,
        use_container_width=True,
    )


# Generic categorical chart
if categorical_columns:
    st.subheader("Categorical Analysis")

    selected_category = st.selectbox(
        "Choose a categorical column",
        options=categorical_columns,
    )

    category_counts = (
        filtered_df[selected_category]
        .astype(str)
        .value_counts()
        .head(20)
        .rename_axis(selected_category)
        .reset_index(name="Count")
    )

    categorical_chart = px.bar(
        category_counts,
        x=selected_category,
        y="Count",
        title=f"Top values in {selected_category}",
    )

    st.plotly_chart(
        categorical_chart,
        use_container_width=True,
    )


# Churn-specific analysis
if churn_column:
    st.subheader("Churn / Outcome Analysis")

    churn_counts = (
        filtered_df[churn_column]
        .astype(str)
        .value_counts()
        .rename_axis(churn_column)
        .reset_index(name="Customers")
    )

    churn_chart = px.pie(
        churn_counts,
        names=churn_column,
        values="Customers",
        hole=0.45,
        title=f"Distribution of {churn_column}",
    )

    st.plotly_chart(
        churn_chart,
        use_container_width=True,
    )


# Contract versus churn analysis
contract_column = mappings["contract"]

if churn_column and contract_column:
    st.subheader("Outcome by Contract")

    contract_churn = (
        filtered_df.groupby(
            [contract_column, churn_column],
            dropna=False,
        )
        .size()
        .reset_index(name="Customers")
    )

    contract_chart = px.bar(
        contract_churn,
        x=contract_column,
        y="Customers",
        color=churn_column,
        barmode="group",
        title=(
            f"{churn_column} by {contract_column}"
        ),
    )

    st.plotly_chart(
        contract_chart,
        use_container_width=True,
    )


# Scatter analysis
if len(numeric_columns) >= 2:
    st.subheader("Relationship Analysis")

    scatter_col1, scatter_col2 = st.columns(2)

    x_column = scatter_col1.selectbox(
        "Horizontal axis",
        numeric_columns,
        index=0,
    )

    y_default = 1 if len(numeric_columns) > 1 else 0

    y_column = scatter_col2.selectbox(
        "Vertical axis",
        numeric_columns,
        index=y_default,
    )

    color_column = churn_column

    scatter_chart = px.scatter(
        filtered_df,
        x=x_column,
        y=y_column,
        color=color_column,
        hover_name=customer_column,
        title=f"{y_column} versus {x_column}",
    )

    st.plotly_chart(
        scatter_chart,
        use_container_width=True,
    )


# Download cleaned data
st.subheader("Export")

csv_data = filtered_df.to_csv(
    index=False,
).encode("utf-8")

st.download_button(
    label="Download cleaned dataset",
    data=csv_data,
    file_name="cleaned_dataset.csv",
    mime="text/csv",
)
# =====================================================
# AUTOMATIC VISUALIZATION ENGINE
# =====================================================

st.divider()

st.header("📊 Automatic Data Visualizer")

if numeric_columns:

    selected_column = st.selectbox(
        "Choose a numeric column",
        numeric_columns,
        key="numeric_column_selector"
    )

    chart_type = st.selectbox(
        "Chart Type",
        [
            "Histogram",
            "Box Plot",
            "Bar Chart"
        ],
        key="chart_type_selector"
    )

    if chart_type == "Histogram":

        fig = px.histogram(
            df,
            x=selected_column,
            nbins=30,
            title=f"Distribution of {selected_column}"
        )

    elif chart_type == "Box Plot":

        fig = px.box(
            df,
            y=selected_column,
            title=f"Box Plot of {selected_column}"
        )

    else:

        summary = (
            df[selected_column]
            .value_counts()
            .head(20)
            .reset_index()
        )

        summary.columns = [selected_column, "Count"]

        fig = px.bar(
            summary,
            x=selected_column,
            y="Count",
            title=f"Top Values in {selected_column}"
        )

    st.plotly_chart(
    fig,
    use_container_width=True,
    key="automatic_visualizer_chart"
)

else:

    st.info("No numeric columns detected.")