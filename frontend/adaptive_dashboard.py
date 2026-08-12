from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_option_menu import option_menu
import joblib
import sys
from pathlib import Path
import shap
import numpy as np

st.set_page_config(
    page_title="Adaptive Customer Analytics",
    page_icon="📊",
    layout="wide",
)
# =====================================================
# PROJECT PATHS
# =====================================================

FRONTEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FRONTEND_DIR.parent
ML_DIR = PROJECT_ROOT / "ml"

if str(ML_DIR) not in sys.path:
    sys.path.append(str(ML_DIR))

from recommend_actions import (
    get_risk_tier,
    get_recommendations,
)
# =====================================================
# CHURN V2 MODEL
# =====================================================

@st.cache_resource
def load_churn_intelligence():

    model_path = (
        PROJECT_ROOT
        / "ml"
        / "churn_model_v2.pkl"
    )

    config_path = (
        PROJECT_ROOT
        / "ml"
        / "champion_config.pkl"
    )

    model = joblib.load(
        model_path
    )

    config = joblib.load(
        config_path
    )

    return model, config


try:

    churn_model_v2, champion_config = (
        load_churn_intelligence()
    )

    CHURN_THRESHOLD = float(
        champion_config["threshold"]
    )

    CHURN_V2_AVAILABLE = True

except Exception as error:

    CHURN_V2_AVAILABLE = False

    churn_model_v2 = None
    champion_config = None
    CHURN_THRESHOLD = 0.33

    CHURN_V2_ERROR = str(error)
    # =====================================================
# CUSTOMER RISK PREDICTION
# =====================================================

def predict_customer_risk(customer_df):

    probability = (
        churn_model_v2
        .predict_proba(customer_df)[0, 1]
    )

    risk_tier = get_risk_tier(
        probability
    )

    customer_dict = (
        customer_df
        .iloc[0]
        .to_dict()
    )

    recommendations = get_recommendations(
        customer_dict,
        risk_tier,
    )

    return {
        "probability": probability,
        "risk_tier": risk_tier,
        "recommendations": recommendations,
    }

# =====================================================
# PROJECT PATHS
# =====================================================

FRONTEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FRONTEND_DIR.parent
ML_DIR = PROJECT_ROOT / "ml"

if str(ML_DIR) not in sys.path:
    sys.path.append(str(ML_DIR))

from recommend_actions import (
    get_risk_tier,
    get_recommendations,
)
# ==========================================
# Premium Sidebar
# ==========================================

with st.sidebar:

    st.image(
        "https://raw.githubusercontent.com/github/explore/main/topics/python/python.png",
        width=80
    )

    st.title("InsightFlow AI")

    st.caption(
        "AI Business Intelligence Platform"
    )

    selected = option_menu(

        None,

        [
            "Dashboard",
            "AI Insights",
            "Analytics",
            "Reports",
            "Settings"
        ],

        icons=[
            "house",
            "robot",
            "bar-chart",
            "file-earmark-text",
            "gear"
        ],

        default_index=0,

        styles={

            "container":{
                "padding":"5px",
                "background-color":"#161b22"
            },

            "icon":{
                "color":"#22c55e",
                "font-size":"18px"
            },

            "nav-link":{
                "font-size":"16px",
                "text-align":"left",
                "margin":"5px",
                "--hover-color":"#2d3748"
            },

            "nav-link-selected":{
                "background-color":"#2563eb"
            }

        }

    )
# =====================================================
# PAGE ROUTING
# =====================================================

if selected == "Analytics":

    st.title("📈 Analytics")
    st.info("Advanced analytics page coming next.")

    st.stop()


elif selected == "Reports":

    st.title("📄 Reports")
    st.info("Executive reporting page coming next.")

    st.stop()


elif selected == "Settings":

    st.title("⚙️ Settings")
    st.info("Application settings coming next.")

    st.stop()
    
    if selected == "Dashboard":       
            st.title("🚀 InsightFlow AI")

            st.markdown("""
        ### Adaptive Business Intelligence Platform

        Upload **any CSV or Excel dataset** and automatically generate:

        - 📊 Executive KPIs
        - 🤖 AI-powered insights
        - 📈 Interactive dashboards
        - 💼 Customer intelligence
        - 📑 Business analytics
        """)

    st.divider()


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

    def generate_executive_summary(
        df: pd.DataFrame,
        numeric_columns: list[str],
        categorical_columns: list[str],
        mappings: dict[str, str | None],
    ) -> list[str]:

        insights = []

        row_count = len(df)
        column_count = len(df.columns)
        missing_values = int(df.isna().sum().sum())
        duplicate_rows = int(df.duplicated().sum())

        insights.append(
            f"The dataset contains {row_count:,} records across "
            f"{column_count} columns."
        )

        if missing_values == 0:
            insights.append("No missing values were detected.")
        else:
            insights.append(
                f"{missing_values:,} missing values were detected."
            )

        if duplicate_rows == 0:
            insights.append("No duplicate rows were detected.")
        else:
            insights.append(
                f"{duplicate_rows:,} duplicate rows were detected."
            )

        churn_column = mappings.get("churn")

        if churn_column and churn_column in df.columns:
            churn_rate = calculate_positive_rate(df[churn_column])

            insights.append(
                f"The detected churn rate is {churn_rate:.1f}%."
            )

        revenue_column = mappings.get("revenue")

        if revenue_column and revenue_column in df.columns:
            revenue_values = pd.to_numeric(
                df[revenue_column],
                errors="coerce",
            )

            if revenue_values.notna().any():
                insights.append(
                    f"Average {revenue_column} is "
                    f"{revenue_values.mean():,.2f}."
                )

        tenure_column = mappings.get("tenure")

        if tenure_column and tenure_column in df.columns:
            tenure_values = pd.to_numeric(
                df[tenure_column],
                errors="coerce",
            )

            if tenure_values.notna().any():
                insights.append(
                    f"Average {tenure_column} is "
                    f"{tenure_values.mean():,.1f}."
                )

        if len(numeric_columns) >= 2:
            correlation_matrix = df[numeric_columns].corr(
                numeric_only=True
            )

            pairs = []

            for i, first_column in enumerate(numeric_columns):
                for second_column in numeric_columns[i + 1:]:
                    value = correlation_matrix.loc[
                        first_column,
                        second_column,
                    ]

                    if pd.notna(value):
                        pairs.append(
                            (
                                abs(float(value)),
                                first_column,
                                second_column,
                            )
                        )

            if pairs:
                strongest = max(pairs, key=lambda item: item[0])

                insights.append(
                    f"The strongest numeric relationship is between "
                    f"{strongest[1]} and {strongest[2]} "
                    f"(correlation {strongest[0]:.2f})."
                )

        return insights

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

    executive_insights = generate_executive_summary(
        df=df,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        mappings=mappings,
    )
    st.subheader("🤖 Executive Summary")

    with st.container(border=True):
        for insight in executive_insights:
            st.markdown(f"- {insight}")
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
    # =====================================================
# CUSTOMER RISK INTELLIGENCE
# =====================================================
if selected == "AI Insights":

    st.subheader("🧠 Customer Risk Intelligence")

if not CHURN_V2_AVAILABLE:

    st.warning(
        "Churn V2 model is currently unavailable."
    )

    st.error(
        f"Model loading error: {CHURN_V2_ERROR}"
    )

else:
    st.success(
        "Gradient Boosting churn intelligence is active."
    )

    st.caption(
        f"Intervention threshold: {CHURN_THRESHOLD:.2f}"
    )
    # =====================================================
# CUSTOMER SELECTION
# =====================================================

if CHURN_V2_AVAILABLE:

    st.markdown("### 👤 Customer Analysis")

    DATA_PATH = (
        PROJECT_ROOT
        / "data"
        / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
    )

    @st.cache_data
    def load_churn_dataset():
        df = pd.read_csv(DATA_PATH)

        # Same cleaning used during model training
        df["TotalCharges"] = pd.to_numeric(
            df["TotalCharges"],
            errors="coerce"
        )

        return df

    customer_data = load_churn_dataset()

    selected_customer_id = st.selectbox(
        "Select Customer",
        customer_data["customerID"].tolist(),
    )

    selected_customer = customer_data[
        customer_data["customerID"]
        == selected_customer_id
    ].iloc[0]

    st.caption(
        f"Customer ID: {selected_customer_id}"
    )
    # =====================================================
# LIVE CUSTOMER RISK PREDICTION
# =====================================================

model_input = (
    selected_customer
    .drop(
        labels=[
            "customerID",
            "Churn",
        ]
    )
    .to_frame()
    .T
)

prediction_result = predict_customer_risk(
    model_input
)

churn_probability = prediction_result[
    "probability"
]

risk_tier = prediction_result[
    "risk_tier"
]

recommendations = prediction_result[
    "recommendations"
]
# =====================================================
# PREMIUM CUSTOMER RISK CARDS
# =====================================================

risk_percentage = churn_probability * 100

risk_icons = {
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🟠",
    "CRITICAL": "🔴",
}

risk_icon = risk_icons.get(
    risk_tier,
    "⚪",
)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f"""<div class="risk-card">
<div class="risk-label">Predicted Churn Risk</div>
<div class="risk-value">{risk_percentage:.1f}%</div>
<div class="risk-caption">Gradient Boosting V2</div>
</div>""",
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""<div class="risk-card">
<div class="risk-label">Risk Tier</div>
<div class="risk-value">{risk_icon} {risk_tier}</div>
<div class="risk-caption">Customer risk segmentation</div>
</div>""",
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""<div class="risk-card">
<div class="risk-label">Intervention Threshold</div>
<div class="risk-value">{CHURN_THRESHOLD * 100:.0f}%</div>
<div class="risk-caption">Retention-action cutoff</div>
</div>""",
        unsafe_allow_html=True,
    )
    st.markdown("### 🎯 Recommended CSM Actions")
    # =====================================================
# CUSTOMER RISK POSITION
# =====================================================

st.markdown("### 📊 Customer Risk Position")

st.progress(
    min(
        max(churn_probability, 0.0),
        1.0,
    )
)

st.caption(
    f"Model score: {risk_percentage:.1f}% • "
    f"Intervention begins at "
    f"{CHURN_THRESHOLD * 100:.0f}%"
)

        # =====================================================
# RECOMMENDED CSM ACTIONS
# =====================================================

st.markdown("### 🎯 Recommended CSM Actions")

for number, action in enumerate(
    recommendations,
    start=1,
):
    st.markdown(
        f"**{number}.** {action}"
    )
    # =====================================================
# CUSTOMER RISK POSITION
# =====================================================

st.markdown("#### Customer Risk Position")

st.progress(
    min(
        max(churn_probability, 0.0),
        1.0,
    )
)

st.caption(
    f"Model score: {risk_percentage:.1f}% • "
    f"Intervention begins at "
    f"{CHURN_THRESHOLD * 100:.0f}%"
)

for action in recommendations:
    st.markdown(f"- {action}")
    # =====================================================
# CUSTOMER-LEVEL SHAP EXPLANATION
# =====================================================

preprocessor = churn_model_v2.named_steps["preprocessor"]
classifier = churn_model_v2.named_steps["classifier"]

X_transformed = preprocessor.transform(
    model_input
)

feature_names = preprocessor.get_feature_names_out()

feature_names = [
    name.replace("numeric__", "")
        .replace("categorical__", "")
    for name in feature_names
]

explainer = shap.TreeExplainer(
    classifier
)

shap_values = explainer.shap_values(
    X_transformed
)

if isinstance(shap_values, list):
    shap_values = shap_values[1]

shap_values = np.array(
    shap_values
).reshape(-1)

shap_df = pd.DataFrame({
    "Feature": feature_names,
    "SHAP Value": shap_values,
})

shap_df["Impact"] = (
    shap_df["SHAP Value"]
    .abs()
)

shap_df = (
    shap_df
    .sort_values(
        "Impact",
        ascending=False,
    )
    .reset_index(drop=True)
)
# =====================================================
# CUSTOMER RISK DRIVERS
# =====================================================

st.markdown("### 🔍 Customer Risk Drivers")

st.caption(
    "Model-specific factors influencing this customer's "
    "predicted churn risk."
)

top_drivers = shap_df.head(5)

for _, row in top_drivers.iterrows():

    feature = (
        str(row["Feature"])
        .replace("_", " ")
    )

    shap_value = float(
        row["SHAP Value"]
    )

    if shap_value > 0:
        st.markdown(
            f"🔺 **{feature}** — contributes to higher predicted churn risk."
        )
    else:
        st.markdown(
            f"🔻 **{feature}** — contributes to lower predicted churn risk."
        )
# =====================================================
# WHY THIS CUSTOMER?
# =====================================================

st.markdown("### 🔍 Why is this customer at risk?")

top_drivers = shap_df.head(5)

for _, row in top_drivers.iterrows():

    feature = row["Feature"]
    shap_value = row["SHAP Value"]

    if shap_value > 0:
        direction = "🔺 increases predicted churn risk"
    else:
        direction = "🔻 reduces predicted churn risk"

    st.markdown(
        f"**{feature}** — {direction}"
    )