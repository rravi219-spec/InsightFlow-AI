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
    page_title="InsightFlow AI | Customer Churn Intelligence",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .insightflow-page-header {
        margin-bottom: 1.5rem;
    }
    .insightflow-page-title {
        color: #f8fafc;
        font-size: 2.15rem;
        font-weight: 750;
        line-height: 1.15;
        margin: 0;
    }
    .insightflow-page-subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin: 0.55rem 0 0;
        max-width: 850px;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #161b22, #111827);
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        min-height: 112px;
    }
    div[data-testid="stMetricLabel"] {
        color: #94a3b8;
    }
    div[data-testid="stMetricValue"] {
        color: #f8fafc;
    }
    .risk-card {
        background: linear-gradient(145deg, #161b22, #111827);
        border: 1px solid #2d3748;
        border-radius: 14px;
        min-height: 138px;
        padding: 1.15rem 1.25rem;
    }
    .risk-label {
        color: #94a3b8;
        font-size: 0.86rem;
        font-weight: 600;
    }
    .risk-value {
        color: #f8fafc;
        font-size: 1.8rem;
        font-weight: 750;
        margin: 0.35rem 0;
    }
    .risk-caption {
        color: #64748b;
        font-size: 0.8rem;
    }
    div[data-testid="stPlotlyChart"],
    div[data-testid="stDataFrame"] {
        margin-bottom: 1rem;
    }
    section[data-testid="stSidebar"] [data-testid="stImage"] {
        margin-bottom: 0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def show_page_header(icon: str, title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="insightflow-page-header">
            <h1 class="insightflow-page-title">{icon} {title}</h1>
            <p class="insightflow-page-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
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


def predict_customer_record(customer_row):
    """Reuse V2 inference for one Telco customer without changing the model."""

    if not CHURN_V2_AVAILABLE:
        return None

    try:
        model_input = (
            customer_row.drop(
                labels=[
                    "customerID",
                    "Churn",
                    "Churn Binary",
                    "Tenure Band",
                ],
                errors="ignore",
            )
            .to_frame()
            .T
        )
        return predict_customer_risk(model_input)
    except Exception:
        return None


def get_customer_record(customer_df, customer_id):
    customer_match = customer_df[
        customer_df["customerID"].astype(str) == str(customer_id)
    ]

    if customer_match.empty:
        return None

    return customer_match.iloc[0]


def render_customer_summary(customer_row):
    prediction = predict_customer_record(customer_row)

    st.subheader("Customer Summary")

    summary_fields = [
        ("Customer ID", "customerID"),
        ("Tenure", "tenure"),
        ("Contract", "Contract"),
        ("Monthly Charges", "MonthlyCharges"),
        ("Total Charges", "TotalCharges"),
        ("Internet Service", "InternetService"),
        ("Payment Method", "PaymentMethod"),
        ("Tech Support", "TechSupport"),
        ("Online Security", "OnlineSecurity"),
        ("Actual Churn", "Churn"),
    ]

    summary_rows = []
    for label, column in summary_fields:
        value = customer_row.get(column, "Not available")

        if column == "tenure" and pd.notna(value):
            value = f"{float(value):.0f} months"
        elif column in {"MonthlyCharges", "TotalCharges"} and pd.notna(value):
            value = f"${float(value):,.2f}"
        elif pd.isna(value):
            value = "Not available"

        summary_rows.append({"Customer Detail": label, "Value": value})

    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
    )

    if prediction is not None:
        prediction_columns = st.columns(2)
        prediction_columns[0].metric(
            "Predicted Churn Probability",
            f"{prediction['probability'] * 100:.1f}%",
        )
        prediction_columns[1].metric("Risk Tier", prediction["risk_tier"])
        st.caption(
            "Predicted risk is a decision-support output from Gradient "
            "Boosting V2 and does not imply causality."
        )
    elif not CHURN_V2_AVAILABLE:
        st.info("V2 predicted risk is unavailable in this session.")


def render_customer_comparison(customer_df):
    st.divider()
    st.subheader("👥 Customer Comparison")
    st.caption(
        "Compare two customer profiles and model risk assessments side by side."
    )

    customer_ids = customer_df["customerID"].dropna().astype(str).tolist()
    if len(customer_ids) < 2:
        st.info("At least two customers are required for comparison.")
        return

    comparison_columns = st.columns(2)
    customer_a_id = comparison_columns[0].selectbox(
        "Customer A",
        customer_ids,
        index=0,
        key="analytics_customer_a",
    )
    customer_b_id = comparison_columns[1].selectbox(
        "Customer B",
        customer_ids,
        index=1,
        key="analytics_customer_b",
    )

    if customer_a_id == customer_b_id:
        st.warning("Select two different customers to create a comparison.")
        return

    customer_a = get_customer_record(customer_df, customer_a_id)
    customer_b = get_customer_record(customer_df, customer_b_id)
    if customer_a is None or customer_b is None:
        st.warning("One of the selected customer records could not be found.")
        return

    prediction_a = predict_customer_record(customer_a)
    prediction_b = predict_customer_record(customer_b)

    comparison_fields = [
        ("Customer ID", "customerID"),
        ("Tenure", "tenure"),
        ("Contract", "Contract"),
        ("Monthly Charges", "MonthlyCharges"),
        ("Total Charges", "TotalCharges"),
        ("Internet Service", "InternetService"),
        ("Payment Method", "PaymentMethod"),
        ("Tech Support", "TechSupport"),
        ("Online Security", "OnlineSecurity"),
        ("Paperless Billing", "PaperlessBilling"),
        ("Actual Churn", "Churn"),
    ]

    comparison_rows = []
    for label, column in comparison_fields:
        value_a = customer_a.get(column, "Not available")
        value_b = customer_b.get(column, "Not available")

        if column == "tenure":
            value_a = f"{float(value_a):.0f} months"
            value_b = f"{float(value_b):.0f} months"
        elif column in {"MonthlyCharges", "TotalCharges"}:
            value_a = f"${float(value_a):,.2f}" if pd.notna(value_a) else "Not available"
            value_b = f"${float(value_b):,.2f}" if pd.notna(value_b) else "Not available"

        comparison_rows.append(
            {"Metric": label, "Customer A": value_a, "Customer B": value_b}
        )

    if prediction_a is not None and prediction_b is not None:
        comparison_rows.extend(
            [
                {
                    "Metric": "Predicted Churn Probability",
                    "Customer A": f"{prediction_a['probability'] * 100:.1f}%",
                    "Customer B": f"{prediction_b['probability'] * 100:.1f}%",
                },
                {
                    "Metric": "Risk Tier",
                    "Customer A": prediction_a["risk_tier"],
                    "Customer B": prediction_b["risk_tier"],
                },
                {
                    "Metric": "Intervention Threshold Position",
                    "Customer A": (
                        "Above threshold"
                        if prediction_a["probability"] >= CHURN_THRESHOLD
                        else "Below threshold"
                    ),
                    "Customer B": (
                        "Above threshold"
                        if prediction_b["probability"] >= CHURN_THRESHOLD
                        else "Below threshold"
                    ),
                },
            ]
        )

    st.dataframe(
        pd.DataFrame(comparison_rows),
        use_container_width=True,
        hide_index=True,
    )

    if prediction_a is not None and prediction_b is not None:
        risk_comparison = pd.DataFrame(
            {
                "Customer": ["Customer A", "Customer B"],
                "Predicted Churn Probability": [
                    prediction_a["probability"] * 100,
                    prediction_b["probability"] * 100,
                ],
            }
        )
        comparison_chart = px.bar(
            risk_comparison,
            x="Customer",
            y="Predicted Churn Probability",
            color="Customer",
            text="Predicted Churn Probability",
            title="Predicted Churn Risk Comparison",
            labels={"Predicted Churn Probability": "Predicted Risk (%)"},
            template="plotly_dark",
        )
        comparison_chart.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="outside",
        )
        comparison_chart.add_hline(
            y=CHURN_THRESHOLD * 100,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text="33% intervention threshold",
        )
        comparison_chart.update_layout(showlegend=False)
        st.plotly_chart(comparison_chart, use_container_width=True)

    st.markdown("### 🔍 Key Differences")
    differences = []

    if customer_a.get("tenure") != customer_b.get("tenure"):
        shorter = "Customer A" if customer_a["tenure"] < customer_b["tenure"] else "Customer B"
        longer = "Customer B" if shorter == "Customer A" else "Customer A"
        differences.append(f"{shorter} has shorter tenure than {longer}.")

    monthly_charges_a = customer_a.get("MonthlyCharges")
    monthly_charges_b = customer_b.get("MonthlyCharges")
    if (
        pd.notna(monthly_charges_a)
        and pd.notna(monthly_charges_b)
        and monthly_charges_a != monthly_charges_b
    ):
        higher_charges = (
            "Customer A"
            if monthly_charges_a > monthly_charges_b
            else "Customer B"
        )
        differences.append(f"{higher_charges} has higher monthly charges.")

    for label, column in [
        ("contract", "Contract"),
        ("internet service", "InternetService"),
        ("payment method", "PaymentMethod"),
        ("Tech Support", "TechSupport"),
        ("Online Security", "OnlineSecurity"),
    ]:
        if customer_a.get(column) != customer_b.get(column):
            differences.append(
                f"The customers differ in {label}: Customer A has "
                f"{customer_a.get(column)}, while Customer B has "
                f"{customer_b.get(column)}."
            )

    if prediction_a is not None and prediction_b is not None:
        if prediction_a["probability"] != prediction_b["probability"]:
            higher_risk = (
                "Customer A"
                if prediction_a["probability"] > prediction_b["probability"]
                else "Customer B"
            )
            differences.append(
                f"{higher_risk} has the higher predicted churn probability."
            )

    with st.container(border=True):
        if differences:
            for difference in differences:
                st.markdown(f"- {difference}")
        else:
            st.write("No material differences were found in the compared fields.")

    st.markdown("### 🎯 Comparison Takeaway")
    with st.container(border=True):
        if prediction_a is not None and prediction_b is not None:
            probability_gap = abs(
                prediction_a["probability"] - prediction_b["probability"]
            ) * 100

            if prediction_a["probability"] > prediction_b["probability"]:
                st.write(
                    "Customer A has a predicted churn risk "
                    f"{probability_gap:.1f} percentage points higher than "
                    "Customer B."
                )
            elif prediction_b["probability"] > prediction_a["probability"]:
                st.write(
                    "Customer B has a predicted churn risk "
                    f"{probability_gap:.1f} percentage points higher than "
                    "Customer A."
                )
            else:
                st.write(
                    "Customer A and Customer B have the same predicted "
                    "churn probability."
                )
        else:
            st.info(
                "A predicted-risk takeaway is unavailable because V2 "
                "inference could not be generated for both customers."
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
        "Customer Churn Intelligence Platform"
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
# PAGE VIEWS
# =====================================================

def show_analytics():

    show_page_header(
        "📈",
        "Customer Analytics",
        "Explore customer-base churn patterns across contracts, payment "
        "methods, services, tenure, and monthly charges.",
    )

    analytics_data_path = (
        PROJECT_ROOT
        / "data"
        / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
    )

    @st.cache_data
    def load_analytics_dataset():
        analytics_df = pd.read_csv(analytics_data_path)
        analytics_df["TotalCharges"] = pd.to_numeric(
            analytics_df["TotalCharges"],
            errors="coerce",
        )
        return analytics_df

    try:
        analytics_df = load_analytics_dataset().copy()

        required_columns = {
            "customerID",
            "Churn",
            "Contract",
            "PaymentMethod",
            "InternetService",
            "tenure",
            "MonthlyCharges",
        }

        if not required_columns.issubset(analytics_df.columns):
            st.error(
                "Customer analytics is unavailable because the source "
                "dataset does not contain all required fields."
            )
            return

        analytics_df["Churn Binary"] = (
            analytics_df["Churn"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({"yes": 1, "no": 0})
        )

        analytics_df["MonthlyCharges"] = pd.to_numeric(
            analytics_df["MonthlyCharges"],
            errors="coerce",
        )
        analytics_df["tenure"] = pd.to_numeric(
            analytics_df["tenure"],
            errors="coerce",
        )

    except Exception:
        st.error(
            "Customer analytics could not be loaded. Please verify that "
            "the Telco churn dataset is available and readable."
        )
        return

    customer_ids = analytics_df["customerID"].dropna().astype(str).tolist()
    view_customer = st.selectbox(
        "Customer View",
        ["All Customers"] + customer_ids,
        key="analytics_customer_view",
        help="Keep the aggregate view or focus on one customer record.",
    )

    if view_customer != "All Customers":
        selected_record = get_customer_record(analytics_df, view_customer)
        if selected_record is None:
            st.warning("The selected customer record could not be found.")
        else:
            render_customer_summary(selected_record)

        render_customer_comparison(analytics_df)
        return

    valid_churn = analytics_df["Churn Binary"].notna()
    total_customers = len(analytics_df)
    overall_churn_rate = (
        analytics_df.loc[valid_churn, "Churn Binary"].mean() * 100
    )
    average_monthly_charges = analytics_df["MonthlyCharges"].mean()
    average_tenure = analytics_df["tenure"].mean()
    churned_customers = int(
        analytics_df["Churn Binary"].fillna(0).sum()
    )

    st.subheader("Executive Analytics KPIs")

    kpi_columns = st.columns(5)
    kpi_columns[0].metric("Total Customers", f"{total_customers:,}")
    kpi_columns[1].metric("Overall Churn Rate", f"{overall_churn_rate:.1f}%")
    kpi_columns[2].metric(
        "Average Monthly Charges",
        f"${average_monthly_charges:,.2f}",
    )
    kpi_columns[3].metric("Average Tenure", f"{average_tenure:.1f} months")
    kpi_columns[4].metric("Churned Customers", f"{churned_customers:,}")

    st.divider()

    def churn_rate_summary(column: str) -> pd.DataFrame:
        return (
            analytics_df.dropna(subset=[column, "Churn Binary"])
            .groupby(column, as_index=False, observed=True)
            .agg(
                Customers=("customerID", "count"),
                Churn_Rate=("Churn Binary", "mean"),
            )
            .assign(Churn_Rate=lambda frame: frame["Churn_Rate"] * 100)
        )

    st.subheader("Churn by Contract Type")
    st.caption(
        "Month-to-month agreements can be compared with longer commitments "
        "to identify where retention pressure is greatest."
    )

    contract_order = ["Month-to-month", "One year", "Two year"]
    contract_summary = churn_rate_summary("Contract")
    contract_summary["Contract"] = pd.Categorical(
        contract_summary["Contract"],
        categories=contract_order,
        ordered=True,
    )
    contract_summary = contract_summary.sort_values("Contract")

    contract_chart = px.bar(
        contract_summary,
        x="Contract",
        y="Churn_Rate",
        color="Churn_Rate",
        text="Churn_Rate",
        labels={"Churn_Rate": "Churn Rate (%)"},
        category_orders={"Contract": contract_order},
        color_continuous_scale="Blues",
        template="plotly_dark",
        title="Customer Churn Rate by Contract Type",
    )
    contract_chart.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    contract_chart.update_layout(coloraxis_showscale=False)
    st.plotly_chart(contract_chart, use_container_width=True)

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Churn by Payment Method")
        st.caption(
            "Compares retention outcomes across the ways customers pay."
        )
        payment_summary = churn_rate_summary("PaymentMethod").sort_values(
            "Churn_Rate",
            ascending=False,
        )
        payment_chart = px.bar(
            payment_summary,
            x="PaymentMethod",
            y="Churn_Rate",
            color="Churn_Rate",
            labels={
                "PaymentMethod": "Payment Method",
                "Churn_Rate": "Churn Rate (%)",
            },
            color_continuous_scale="Tealgrn",
            template="plotly_dark",
            title="Customer Churn Rate by Payment Method",
        )
        payment_chart.update_layout(coloraxis_showscale=False)
        st.plotly_chart(payment_chart, use_container_width=True)

    with chart_col2:
        st.subheader("Churn by Internet Service")
        st.caption(
            "Highlights differences in churn across internet-service types."
        )
        internet_summary = churn_rate_summary("InternetService").sort_values(
            "Churn_Rate",
            ascending=False,
        )
        internet_chart = px.bar(
            internet_summary,
            x="InternetService",
            y="Churn_Rate",
            color="InternetService",
            labels={
                "InternetService": "Internet Service",
                "Churn_Rate": "Churn Rate (%)",
            },
            template="plotly_dark",
            title="Customer Churn Rate by Internet Service",
        )
        internet_chart.update_layout(showlegend=False)
        st.plotly_chart(internet_chart, use_container_width=True)

    analytics_df["Tenure Band"] = pd.cut(
        analytics_df["tenure"],
        bins=[-1, 12, 24, 48, float("inf")],
        labels=["0–12 months", "13–24 months", "25–48 months", "49+ months"],
    )

    tenure_order = [
        "0–12 months",
        "13–24 months",
        "25–48 months",
        "49+ months",
    ]
    tenure_summary = churn_rate_summary("Tenure Band")

    st.subheader("Tenure vs Churn")
    st.caption(
        "Shows how churn changes as customers progress through their lifecycle."
    )
    tenure_chart = px.bar(
        tenure_summary,
        x="Tenure Band",
        y="Churn_Rate",
        color="Churn_Rate",
        text="Churn_Rate",
        labels={"Churn_Rate": "Churn Rate (%)"},
        category_orders={"Tenure Band": tenure_order},
        color_continuous_scale="Blues",
        template="plotly_dark",
        title="Customer Churn Rate by Tenure Band",
    )
    tenure_chart.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    tenure_chart.update_layout(coloraxis_showscale=False)
    st.plotly_chart(tenure_chart, use_container_width=True)

    st.subheader("Monthly Charges vs Churn")
    st.caption(
        "The distribution shows whether churned customers tend to have "
        "different monthly charges from retained customers."
    )
    charges_df = analytics_df.dropna(
        subset=["MonthlyCharges", "Churn Binary"]
    ).copy()
    charges_df["Customer Status"] = charges_df["Churn Binary"].map(
        {0: "Retained", 1: "Churned"}
    )
    charges_chart = px.box(
        charges_df,
        x="Customer Status",
        y="MonthlyCharges",
        color="Customer Status",
        points="outliers",
        labels={"MonthlyCharges": "Monthly Charges"},
        category_orders={"Customer Status": ["Retained", "Churned"]},
        template="plotly_dark",
        title="Monthly Charges for Retained and Churned Customers",
    )
    charges_chart.update_layout(showlegend=False)
    st.plotly_chart(charges_chart, use_container_width=True)

    st.subheader("Customer Segmentation Summary")
    st.caption(
        "Tenure-based segments summarize customer volume and observed churn."
    )
    segment_table = tenure_summary.rename(
        columns={
            "Tenure Band": "Segment",
            "Customers": "Customer Count",
            "Churn_Rate": "Churn Rate",
        }
    )
    segment_table["Churn Rate"] = segment_table["Churn Rate"].map(
        lambda value: f"{value:.1f}%"
    )
    st.dataframe(
        segment_table[["Segment", "Customer Count", "Churn Rate"]],
        use_container_width=True,
        hide_index=True,
    )

    render_customer_comparison(analytics_df)

def show_reports():

    show_page_header(
        "📄",
        "Executive Reports",
        "An executive-level summary of customer health and churn intelligence.",
    )

    reports_data_path = (
        PROJECT_ROOT
        / "data"
        / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
    )
    feature_importance_path = (
        PROJECT_ROOT
        / "ml"
        / "churn_feature_importance.csv"
    )

    @st.cache_data
    def load_reports_dataset():
        reports_df = pd.read_csv(reports_data_path)
        reports_df["TotalCharges"] = pd.to_numeric(
            reports_df["TotalCharges"],
            errors="coerce",
        )
        return reports_df

    @st.cache_data
    def load_feature_importance():
        return pd.read_csv(feature_importance_path)

    try:
        reports_df = load_reports_dataset().copy()

        required_columns = {
            "customerID",
            "Churn",
            "tenure",
            "MonthlyCharges",
        }
        if not required_columns.issubset(reports_df.columns):
            st.error(
                "Executive reporting is unavailable because the customer "
                "dataset does not contain all required fields."
            )
            return

        reports_df["Churn Binary"] = (
            reports_df["Churn"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({"yes": 1, "no": 0})
        )
        reports_df["MonthlyCharges"] = pd.to_numeric(
            reports_df["MonthlyCharges"],
            errors="coerce",
        )
        reports_df["tenure"] = pd.to_numeric(
            reports_df["tenure"],
            errors="coerce",
        )

    except Exception:
        st.error(
            "Executive reporting could not be loaded. Please verify that "
            "the Telco churn dataset is available and readable."
        )
        return

    customer_ids = reports_df["customerID"].dropna().astype(str).tolist()
    view_customer = st.selectbox(
        "Customer View",
        ["All Customers"] + customer_ids,
        key="reports_customer_view",
        help="Keep the executive aggregate view or focus on one customer.",
    )

    if view_customer != "All Customers":
        selected_record = get_customer_record(reports_df, view_customer)
        if selected_record is None:
            st.warning("The selected customer record could not be found.")
        else:
            render_customer_summary(selected_record)
        return

    total_customers = len(reports_df)
    overall_churn_rate = reports_df["Churn Binary"].mean() * 100
    average_monthly_charges = reports_df["MonthlyCharges"].mean()
    average_tenure = reports_df["tenure"].mean()

    high_risk_count = None

    if CHURN_V2_AVAILABLE:
        try:
            report_model_input = reports_df.drop(
                columns=["customerID", "Churn", "Churn Binary"]
            )
            report_probabilities = churn_model_v2.predict_proba(
                report_model_input
            )[:, 1]
            high_risk_count = int(
                np.count_nonzero(report_probabilities >= 0.33)
            )
        except Exception:
            high_risk_count = None

    st.subheader("Executive Summary KPIs")
    report_kpis = st.columns(5)
    report_kpis[0].metric("Total Customers", f"{total_customers:,}")
    report_kpis[1].metric(
        "Overall Churn Rate",
        f"{overall_churn_rate:.1f}%",
    )
    report_kpis[2].metric(
        "Average Monthly Charges",
        f"${average_monthly_charges:,.2f}",
    )
    report_kpis[3].metric(
        "Average Tenure",
        f"{average_tenure:.1f} months",
    )
    report_kpis[4].metric(
        "High / Critical Risk",
        f"{high_risk_count:,}" if high_risk_count is not None else "Unavailable",
    )

    if high_risk_count is None:
        st.caption(
            "High/critical-risk customer count is unavailable because V2 "
            "predictions could not be generated in this session."
        )
    else:
        st.caption(
            "High/critical risk includes customers whose V2 churn probability "
            "meets or exceeds the 0.33 intervention threshold."
        )

    st.divider()
    st.subheader("Champion Model Summary")

    model_summary = pd.DataFrame(
        {
            "Metric": [
                "Champion model",
                "Tuned CV ROC-AUC",
                "Intervention threshold",
                "Recall at optimized threshold",
                "F1 at optimized threshold",
                "Mean calibration gap",
            ],
            "Value": [
                "Gradient Boosting",
                "0.8505",
                "0.33",
                "0.7258",
                "0.6411",
                "0.0182",
            ],
        }
    )
    st.dataframe(
        model_summary,
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Validated model metrics summarize discrimination, intervention "
        "coverage, and calibration performance."
    )

    st.subheader("Validated Risk Tier Summary")

    risk_tier_summary = pd.DataFrame(
        {
            "Risk Tier": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "Actual Churn Rate": [5.53, 24.26, 47.04, 72.29],
        }
    )
    risk_tier_chart = px.bar(
        risk_tier_summary,
        x="Risk Tier",
        y="Actual Churn Rate",
        color="Risk Tier",
        text="Actual Churn Rate",
        category_orders={
            "Risk Tier": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        },
        labels={"Actual Churn Rate": "Actual Churn Rate (%)"},
        color_discrete_map={
            "LOW": "#22c55e",
            "MEDIUM": "#eab308",
            "HIGH": "#f97316",
            "CRITICAL": "#ef4444",
        },
        template="plotly_dark",
        title="Observed Churn Rate by Validated Risk Tier",
    )
    risk_tier_chart.update_traces(
        texttemplate="%{text:.2f}%",
        textposition="outside",
    )
    risk_tier_chart.update_layout(showlegend=False)
    st.plotly_chart(risk_tier_chart, use_container_width=True)
    st.caption(
        "Observed churn increases across the validated model risk tiers, "
        "supporting progressively stronger retention attention."
    )

    st.subheader("Top Churn Drivers")

    feature_importance_df = None
    try:
        loaded_importance = load_feature_importance().copy()
        if {"Feature", "Importance"}.issubset(loaded_importance.columns):
            loaded_importance["Importance"] = pd.to_numeric(
                loaded_importance["Importance"],
                errors="coerce",
            )
            feature_importance_df = (
                loaded_importance.dropna(subset=["Feature", "Importance"])
                .sort_values("Importance", ascending=False)
                .reset_index(drop=True)
            )
    except Exception:
        feature_importance_df = None

    if feature_importance_df is None or feature_importance_df.empty:
        st.info("The model feature-importance report is currently unavailable.")
    else:
        top_features = feature_importance_df.head(10).sort_values("Importance")
        feature_chart = px.bar(
            top_features,
            x="Importance",
            y="Feature",
            orientation="h",
            color="Importance",
            color_continuous_scale="Blues",
            template="plotly_dark",
            title="Top 10 Contributors to the Model Risk Assessment",
        )
        feature_chart.update_layout(coloraxis_showscale=False)
        st.plotly_chart(feature_chart, use_container_width=True)
        st.caption(
            "Feature importance describes contribution to the model’s risk "
            "assessment and should not be interpreted as causal impact."
        )

    st.subheader("Executive Findings")
    executive_findings = [
        (
            "Contract type is strongly associated with predicted churn risk, "
            "with flexible contract structures warranting closer review."
        ),
        (
            "Short-tenure customers show patterns associated with elevated "
            "risk and may benefit from closer lifecycle monitoring."
        ),
        (
            "Support and security service adoption contributes to the model’s "
            "risk assessment and can inform proactive account reviews."
        ),
        (
            "Payment-method patterns are associated with predicted churn risk "
            "and may help identify potentially vulnerable customers."
        ),
    ]
    with st.container(border=True):
        for finding in executive_findings:
            st.markdown(f"- {finding}")

    st.subheader("Export")

    executive_metrics = pd.DataFrame(
        {
            "Metric": [
                "Total Customers",
                "Overall Churn Rate (%)",
                "Average Monthly Charges",
                "Average Tenure (Months)",
                "High / Critical Risk Customers",
            ],
            "Value": [
                total_customers,
                round(overall_churn_rate, 2),
                round(average_monthly_charges, 2),
                round(average_tenure, 2),
                high_risk_count if high_risk_count is not None else "Unavailable",
            ],
        }
    )

    export_columns = st.columns(3)
    export_columns[0].download_button(
        "Download risk tier summary",
        data=risk_tier_summary.to_csv(index=False).encode("utf-8"),
        file_name="risk_tier_summary.csv",
        mime="text/csv",
    )
    export_columns[1].download_button(
        "Download feature importance",
        data=(
            feature_importance_df.to_csv(index=False).encode("utf-8")
            if feature_importance_df is not None
            else b"Feature,Importance\n"
        ),
        file_name="feature_importance.csv",
        mime="text/csv",
        disabled=feature_importance_df is None,
    )
    export_columns[2].download_button(
        "Download executive metrics",
        data=executive_metrics.to_csv(index=False).encode("utf-8"),
        file_name="executive_summary_metrics.csv",
        mime="text/csv",
    )

def show_settings():

    show_page_header(
        "⚙️",
        "Settings",
        "Review model configuration and session display preferences.",
    )

    st.subheader("Model Information")

    model_col1, model_col2 = st.columns(2)
    model_col1.metric("Champion Model", "Gradient Boosting V2")
    model_col2.metric("Current Intervention Threshold", "33%")

    risk_boundaries = pd.DataFrame(
        {
            "Risk Tier": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "Probability Range": [
                "< 15%",
                "15%–33%",
                "33%–60%",
                ">= 60%",
            ],
        }
    )

    st.markdown("#### Risk Tier Boundaries")
    st.dataframe(
        risk_boundaries,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Display Preferences")
    st.caption("These preferences persist for the current Streamlit session.")

    if "show_model_explanations" not in st.session_state:
        st.session_state.show_model_explanations = True

    if "show_csm_actions" not in st.session_state:
        st.session_state.show_csm_actions = True

    if "shap_driver_count" not in st.session_state:
        st.session_state.shap_driver_count = 5

    st.toggle(
        "Show model explanations",
        key="show_model_explanations",
        help="Controls the session preference for explainable-AI content.",
    )
    st.toggle(
        "Show recommended CSM actions",
        key="show_csm_actions",
        help="Controls the session preference for retention recommendations.",
    )
    st.slider(
        "Number of SHAP drivers displayed",
        min_value=3,
        max_value=10,
        key="shap_driver_count",
        help="Select how many customer-level model drivers to display.",
    )

    st.divider()
    st.subheader("Model Status")

    churn_model_loaded = CHURN_V2_AVAILABLE and churn_model_v2 is not None
    champion_config_loaded = champion_config is not None
    shap_available = hasattr(shap, "TreeExplainer")

    status_col1, status_col2, status_col3 = st.columns(3)
    status_col1.metric(
        "Churn Model",
        "Loaded" if churn_model_loaded else "Unavailable",
    )
    status_col2.metric(
        "Champion Config",
        "Loaded" if champion_config_loaded else "Unavailable",
    )
    status_col3.metric(
        "SHAP",
        "Available" if shap_available else "Unavailable",
    )

    st.divider()
    st.subheader("About InsightFlow AI")
    st.write(
        "An adaptive Customer Success and Business Intelligence platform "
        "combining automated analytics, churn prediction, explainable AI, "
        "and retention decision support."
    )

    st.warning(
        "Predictions are decision-support outputs and should not be treated "
        "as causal conclusions."
    )

def show_dashboard():
    show_page_header(
        "🚀",
        "Adaptive Business Intelligence",
        "Upload any CSV or Excel dataset to generate executive KPIs, "
        "adaptive insights, interactive dashboards, and business analytics.",
    )

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
def show_ai_insights():

    show_page_header(
        "🧠",
        "Customer Risk Intelligence",
        "Understand individual churn risk, model drivers, and recommended "
        "Customer Success actions.",
    )

    if not CHURN_V2_AVAILABLE:

        st.warning(
            "Churn V2 model is currently unavailable."
        )

        st.error(
            f"Model loading error: {CHURN_V2_ERROR}"
        )

        return

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

    st.divider()

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

    if st.session_state.get("show_csm_actions", True):
        st.markdown("### 🎯 Recommended CSM Actions")

        with st.container(border=True):
            for number, action in enumerate(
                recommendations,
                start=1,
            ):
                st.markdown(
                    f"**{number}.** {action}"
                )

    st.divider()

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

    if st.session_state.get("show_model_explanations", True):
        st.markdown("### 🔍 Customer Risk Drivers")

        st.caption(
            "Model-specific factors influencing this customer's "
            "predicted churn risk."
        )

        driver_count = st.session_state.get("shap_driver_count", 5)
        top_drivers = shap_df.head(driver_count)

        with st.container(border=True):
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
                        f"🔺 **{feature}** — contributes to higher predicted "
                        "churn risk."
                    )
                else:
                    st.markdown(
                        f"🔻 **{feature}** — contributes to lower predicted "
                        "churn risk."
                    )


# =====================================================
# PAGE ROUTING
# =====================================================

if selected == "Dashboard":
    show_dashboard()
elif selected == "AI Insights":
    show_ai_insights()
elif selected == "Analytics":
    show_analytics()
elif selected == "Reports":
    show_reports()
elif selected == "Settings":
    show_settings()
