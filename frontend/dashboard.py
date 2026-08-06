import streamlit as st
import pandas as pd
import requests
from data_analyzer import detect_columns, summarize_dataset

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Customer Success AI",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 Customer Success AI Dashboard")
st.caption(
    "Customer health monitoring, churn-risk identification, "
    "and success recommendations."
)

st.caption(
    "Customer health monitoring, churn-risk identification, "
    "and success recommendations."
)

st.markdown("---")

required_columns = {
    "name",
    "usage",
    "tickets",
    "nps",
}

uploaded_df = None

if uploaded_df is not None:
    missing_columns = required_columns - set(uploaded_df.columns)

    if missing_columns:
        st.error(
            "The uploaded file is missing these columns: "
            + ", ".join(sorted(missing_columns))
        )
        st.stop()

    uploaded_df["health_score"] = (
        uploaded_df["usage"] * 0.5
        + uploaded_df["nps"] * 5
        - uploaded_df["tickets"] * 2
    ).round(2)

    uploaded_df["status"] = uploaded_df["health_score"].apply(
        lambda score: (
            "Healthy"
            if score >= 80
            else "At Risk"
            if score >= 60
            else "Critical"
        )
    )


st.sidebar.header("📂 Dataset Analysis")

uploaded_file = st.sidebar.file_uploader(
    "Upload customer CSV or Excel",
    type=["csv", "xlsx"]
)

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            uploaded_df = pd.read_csv(uploaded_file)
        else:
            uploaded_df = pd.read_excel(uploaded_file)

        st.sidebar.success(
            f"Loaded {len(uploaded_df)} customers."
        )

    except Exception as error:
        st.sidebar.error(f"Error: {error}")

if uploaded_df is not None:
    detected_columns = detect_columns(uploaded_df)
    dataset_summary = summarize_dataset(uploaded_df)

    st.subheader("Dataset Overview")

    overview_col1, overview_col2, overview_col3, overview_col4 = st.columns(4)

    overview_col1.metric(
        "Rows",
        f"{dataset_summary['rows']:,}",
    )

    overview_col2.metric(
        "Columns",
        dataset_summary["columns"],
    )

    overview_col3.metric(
        "Missing Values",
        f"{dataset_summary['missing_values']:,}",
    )

    overview_col4.metric(
        "Duplicate Rows",
        f"{dataset_summary['duplicate_rows']:,}",
    )

    st.subheader("Detected Fields")

    detected_table = pd.DataFrame(
        [
            {
                "Business field": role,
                "Detected column": column or "Not detected",
            }
            for role, column in detected_columns.items()
        ]
    )

    st.dataframe(
        detected_table,
        use_container_width=True,
        hide_index=True,
    )

st.sidebar.header("Add Customer")

with st.sidebar.form("add_customer_form"):
    customer_name = st.text_input("Customer name")

    usage = st.number_input(
        "Usage score",
        min_value=0.0,
        max_value=100.0,
        value=50.0,
        step=1.0,
    )

    tickets = st.number_input(
        "Open tickets",
        min_value=0,
        value=0,
        step=1,
    )

    nps = st.number_input(
        "NPS",
        min_value=0,
        max_value=10,
        value=5,
        step=1,
    )

    renewal_status = st.selectbox(
        "Renewal status",
        ["Likely", "At Risk", "Unknown"],
    )

    submitted = st.form_submit_button("Add Customer")

    if submitted:
        if not customer_name.strip():
            st.error("Please enter a customer name.")
        else:
            payload = {
                "name": customer_name.strip(),
                "usage": usage,
                "tickets": tickets,
                "nps": nps,
                "renewal_status": renewal_status,
            }

            try:
                response = requests.post(
                    f"{API_URL}/customers",
                    json=payload,
                    timeout=10,
                )

                response.raise_for_status()

                st.success(
                    f"{customer_name} was added successfully."
                )

                st.cache_data.clear()
                st.rerun()

            except requests.exceptions.RequestException as error:
                st.error(f"Could not add customer: {error}")

@st.cache_data(ttl=10)
def load_customer_data() -> list[dict]:
    """Retrieve customers and their health scores from FastAPI."""

    customer_response = requests.get(
        f"{API_URL}/customers",
        timeout=10,
    )
    customer_response.raise_for_status()

    customers = customer_response.json()
    results = []

    for customer in customers:
        health_response = requests.get(
            f"{API_URL}/health-score/{customer['id']}",
            timeout=10,
        )
        health_response.raise_for_status()

        health = health_response.json()

        results.append(
            {
                "id": customer["id"],
                "name": customer["name"],
                "usage": customer["usage"],
                "tickets": customer["tickets"],
                "nps": customer["nps"],
                "renewal_status": customer["renewal_status"],
                "health_score": health["health_score"],
                "status": health["status"],
                "recommendation": health.get(
                    "recommendation",
                    "No recommendation available.",
                ),
            }
        )

    return results

customer_data = []

try:
    if uploaded_df is not None:
        df = uploaded_df.copy()
    else:
        customer_data = load_customer_data()
        df = pd.DataFrame(customer_data)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("👥 Customers", len(df))

    with col2:
        if "usage" in df.columns:
            st.metric(
                "❤️ Avg Usage",
                round(df["usage"].mean(), 1),
            )
        elif detected_columns.get("revenue"):
            revenue_column = detected_columns["revenue"]

            st.metric(
                "💰 Avg Monthly Charges",
                round(
                    pd.to_numeric(
                        df[revenue_column],
                        errors="coerce",
                    ).mean(),
                    2,
                ),
            )
        else:
            st.metric("❤️ Avg Usage", "Not available")


    with col3:
        if "tickets" in df.columns:
            st.metric(
                "🎫 Avg Tickets",
                round(df["tickets"].mean(), 1),
            )
        elif detected_columns.get("tenure"):
            tenure_column = detected_columns["tenure"]

            st.metric(
                "📅 Avg Tenure",
                round(
                    pd.to_numeric(
                        df[tenure_column],
                        errors="coerce",
                    ).mean(),
                    1,
                ),
            )
        else:
            st.metric("🎫 Avg Tickets", "Not available")


    with col4:
        if "nps" in df.columns:
            st.metric(
                "⭐ Avg NPS",
                round(df["nps"].mean(), 1),
            )
        elif detected_columns.get("churn"):
            churn_column = detected_columns["churn"]

            churn_rate = (
                df[churn_column]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["yes", "true", "1", "churned"])
                .mean()
                * 100
            )

            st.metric(
                "⚠️ Churn Rate",
                f"{churn_rate:.1f}%",
            )
        else:
            st.metric("⭐ Avg NPS", "Not available")

    st.markdown("---")

except requests.exceptions.ConnectionError:
    st.error(
        "The FastAPI backend is not running. "
        "Start Uvicorn on http://127.0.0.1:8000."
    )
    st.stop()

except requests.exceptions.RequestException as error:
    st.error(f"Could not retrieve customer data: {error}")
    st.stop()


if uploaded_df is None and not customer_data:
    st.warning("No customers found. Add customers through FastAPI `/docs`.")
    st.stop()


# Sidebar filters
st.sidebar.header("Filters")

search_term = st.sidebar.text_input(
    "Search customer",
    placeholder="Enter a customer name",
)

if "status" in df.columns:
    status_column = "status"

elif detected_columns.get("churn"):
    status_column = detected_columns["churn"]

else:
    status_column = None


if status_column is not None:
    status_options = sorted(
        df[status_column]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_statuses = st.sidebar.multiselect(
        "Customer status",
        options=status_options,
        default=status_options,
    )
else:
    selected_statuses = []

filtered_df = df.copy()

if search_term:
    filtered_df = filtered_df[
        filtered_df["name"].str.contains(
            search_term,
            case=False,
            na=False,
        )
    ]

if selected_statuses and status_column is not None:
    filtered_df = filtered_df[
        filtered_df[status_column]
        .astype(str)
        .isin(selected_statuses)
    ]

# KPI cards
total_customers = len(filtered_df)

if "health_score" in filtered_df.columns:
    average_health = filtered_df["health_score"].mean()
    average_health_label = "Average Health"

elif detected_columns.get("revenue"):
    revenue_column = detected_columns["revenue"]

    average_health = pd.to_numeric(
        filtered_df[revenue_column],
        errors="coerce",
    ).mean()

    average_health_label = "Avg Monthly Charges"

elif detected_columns.get("tenure"):
    tenure_column = detected_columns["tenure"]

    average_health = pd.to_numeric(
        filtered_df[tenure_column],
        errors="coerce",
    ).mean()

    average_health_label = "Average Tenure"

else:
    average_health = 0
    average_health_label = "Average Metric"

if "nps" in filtered_df.columns:
    average_nps = filtered_df["nps"].mean()
    average_nps_label = "Average NPS"

elif detected_columns.get("churn"):
    churn_column = detected_columns["churn"]

    average_nps = (
        filtered_df[churn_column]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["yes", "true", "1", "churned"])
        .mean()
        * 100
    )

    average_nps_label = "Churn Rate"

else:
    average_nps = 0
    average_nps_label = "Secondary Metric"


if "tickets" in filtered_df.columns:
    total_tickets = filtered_df["tickets"].sum()
    total_tickets_label = "Open Tickets"

elif detected_columns.get("tenure"):
    tenure_column = detected_columns["tenure"]

    total_tickets = pd.to_numeric(
        filtered_df[tenure_column],
        errors="coerce",
    ).mean()

    total_tickets_label = "Avg Tenure"

else:
    total_tickets = 0
    total_tickets_label = "Additional Metric"

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Customers", total_customers)
col2.metric(average_health_label, f"{average_health:.1f}")
col3.metric("Average NPS", f"{average_nps:.1f}")
col4.metric("Open Tickets", int(total_tickets))

st.divider()

# Customer table
st.subheader("Customer Portfolio")

display_columns = [
    "name",
    "usage",
    "tickets",
    "nps",
    "renewal_status",
    "health_score",
    "status",
]

st.dataframe(
    filtered_df[display_columns],
    use_container_width=True,
    hide_index=True,
)

st.divider()

# Charts
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Customer Health Scores")

    health_chart = px.bar(
        filtered_df.sort_values(
            "health_score",
            ascending=False,
        ),
        x="name",
        y="health_score",
        color="status",
        hover_data=[
            "usage",
            "tickets",
            "nps",
            "renewal_status",
        ],
        labels={
            "name": "Customer",
            "health_score": "Health Score",
            "status": "Status",
        },
    )

    st.plotly_chart(
        health_chart,
        use_container_width=True,
    )

with chart_col2:
    st.subheader("Risk Distribution")

    risk_counts = (
        filtered_df["status"]
        .value_counts()
        .rename_axis("status")
        .reset_index(name="customers")
    )

    risk_chart = px.pie(
        risk_counts,
        names="status",
        values="customers",
        hole=0.45,
    )

    st.plotly_chart(
        risk_chart,
        use_container_width=True,
    )

st.divider()

# Customer recommendation cards
st.subheader("Customer Recommendations")

for _, customer in filtered_df.iterrows():

    if customer["status"] == "Healthy":
        indicator = "🟢"
    elif customer["status"] == "At Risk":
        indicator = "🟡"
    else:
        indicator = "🔴"

    with st.expander(
        f"{indicator} {customer['name']} — "
        f"Health Score: {customer['health_score']}"
    ):
        detail_col1, detail_col2, detail_col3 = st.columns(3)

        detail_col1.metric("Usage", customer["usage"])
        detail_col2.metric("NPS", customer["nps"])
        detail_col3.metric("Tickets", customer["tickets"])

        st.write(f"**Status:** {customer['status']}")
        st.write(
            f"**Renewal status:** "
            f"{customer['renewal_status']}"
        )
        st.info(customer["recommendation"])

if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()