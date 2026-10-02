"""Retail presentation. Business aggregates belong in the analytics API."""
from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import retail_customer_analytics as analytics
from etl.retail_config import DATABASE
from frontend.design_system import (
    apply_design, hero, metric_cards, chart, intelligence_brief, segment_badge,
    rfm_scores, SEGMENT_COLORS,
)

VIEWS = ("Executive Pulse", "Customer Segments", "Retention", "Customer 360")
EXPLANATIONS = {
    "Champions": "Comparatively strong recency, frequency and historical purchase value under the current RFM rules.",
    "Loyal": "Comparatively frequent purchasing with a recency score of at least three under the current rules.",
    "New Customers": "One observed purchase order and a high recency score; true business acquisition is unknown.",
    "Potential Loyalists": "A recency score of at least three, after the higher-priority segment rules.",
    "At Risk": "Previously engaged customer with reduced recent purchasing activity under the current RFM rules.",
    "Hibernating": "Lower recency and frequency scores under the current RFM rules.",
}
QUERIES = {name: getattr(analytics, name) for name in (
    "get_analysis_metadata", "get_customer_kpis", "get_rfm_segment_summary",
    "get_cohort_retention_matrix", "get_repeat_purchase_summary",
    "get_purchase_frequency_distribution", "get_customer_value_concentration",
    "get_median_customer_value", "get_customer_ids", "get_customer_profile",
    "get_customer_history", "get_customer_activity",
)}


def database_version(path):
    # Include WAL changes if a local writer is using WAL mode. No connection is cached.
    files = (path, Path(str(path) + "-wal"))
    return tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None for p in files)


@st.cache_data(ttl=300, max_entries=128, show_spinner=False)
def query(name, path, version, **kwargs):
    return QUERIES[name](db_path=path, **kwargs)


def number(value, decimals=0, suffix="", currency=False):
    if pd.isna(value):
        return "Not available"
    if currency:
        return f"{'-' if value < 0 else ''}£{abs(value):,.{decimals}f}{suffix}"
    return f"{value:,.{decimals}f}{suffix}"


def cards(items):
    metric_cards(items)


def segment_table(data):
    return data.assign(
        customer_pct=data.customer_pct.round(1),
        average_frequency=data.average_frequency.round(2),
        net_value_gbp=(data.net_value_micros / 1_000_000).round(2),
        average_order_value_gbp=data.average_order_value_gbp.round(2),
    )[["segment", "customers", "customer_pct", "net_value_gbp", "average_frequency", "average_order_value_gbp"]].rename(columns={
        "segment": "Segment", "customers": "Customers", "customer_pct": "Customers (%)",
        "net_value_gbp": "Net value (GBP)", "average_frequency": "Orders per purchaser",
        "average_order_value_gbp": "Average order value (GBP)",
    })


def overview(load):
    hero()
    st.subheader("Retail executive pulse")
    k = load("get_customer_kpis").iloc[0]
    cards([
        ("Eligible Purchasers", number(k.known_analytical_customers), "Known customers with at least one qualifying purchase."),
        ("Purchase Orders", number(k.purchase_invoices), "Distinct qualifying customer/invoice pairs, not invoice lines."),
        ("Repeat Purchase Rate", number(k.repeat_purchase_rate_pct, 1, "%"), "Purchasers with two or more orders / all eligible purchasers."),
        ("Gross Purchase Value", number(k.gross_purchase_micros / 1e6, 2, currency=True), "Qualifying purchases before signed adjustments."),
        ("Net Transaction Value", number(k.net_value_micros / 1e6, 2, currency=True), "All known-customer ledger amounts, including return-only customers."),
        ("Average Order Value", number(k.average_order_value_gbp, 2, currency=True), "Gross purchase value / qualifying orders."),
    ])
    st.caption("Historical dataset-derived transaction value in GBP; not audited accounting revenue.")
    segments = load("get_rfm_segment_summary")
    if segments.empty:
        st.info("No qualifying purchasers are available for segment analysis.")
    else:
        chart(px.bar(segments, x="customers", y="segment", orientation="h",
                     color="segment", color_discrete_map=SEGMENT_COLORS,
                     title="How healthy is the customer base?", labels={"customers": "Purchasers", "segment": "RFM segment"}).update_layout(showlegend=False))
    st.subheader("Historical customer value")
    concentration = load("get_customer_value_concentration").iloc[0]
    observations = []
    if not segments.empty:
        largest = segments.sort_values(["customers", "segment"], ascending=[False, True]).iloc[0]
        highest = segments.sort_values(["net_value_micros", "segment"], ascending=[False, True]).iloc[0]
        observations.extend([
            f"{largest.segment} is the largest RFM segment: {number(largest.customers)} purchasers ({number(largest.customer_pct, 1, '%')}).",
            f"{highest.segment} has the highest observed segment net value: {number(highest.net_value_micros / 1e6, 2, currency=True)}.",
        ])
    if pd.notna(k.repeat_purchase_rate_pct):
        observations.append(f"{number(k.repeat_purchase_rate_pct, 1, '%')} of eligible purchasers have at least two observed orders.")
    if pd.notna(concentration.top_10pct_share_pct):
        observations.append(f"The top {number(concentration.top_customer_count)} purchasers account for {number(concentration.top_10pct_share_pct, 1, '%')} of purchaser net value.")
    intelligence_brief(observations)
    median = load("get_median_customer_value").iloc[0].median_net_value_gbp
    cards([
        ("Median Customer Net Value", number(median, 2, currency=True), "All known ledger customers, including return-only customers."),
        ("Top 10% Value Share", number(concentration.top_10pct_share_pct, 1, "%"), "Highest-net-value ceil(10% of purchasers); denominator is purchaser net value."),
        ("Customers in Top Group", number(concentration.top_customer_count), "Ties are resolved deterministically by customer ID."),
    ])
    st.caption("Historical customer value is observed value, not predicted Customer Lifetime Value. Segment and concentration values exclude return-only customers; the headline net value includes them.")


def segments_page(load):
    with st.expander("How to read RFM"):
        st.write("Recency: days since the latest purchase. Frequency: qualifying orders. Monetary: gross qualifying historical purchase value. Scores run from 1 to 5, with 5 highest; ties receive equal scores.")
    st.caption("RFM segments are analytical rules, not ground-truth personas or predicted churn.")
    data = load("get_rfm_segment_summary")
    selected = st.multiselect("Segments to display", data.segment.tolist(), default=data.segment.tolist())
    st.caption("Filter scope: this page's charts and table only. Percentages retain the full purchaser denominator.")
    data = data[data.segment.isin(selected)]
    if data.empty:
        st.info("No segments selected or no qualifying purchasers available.")
        return
    for col, segment in zip(st.columns(len(data)), data.segment):
        with col:
            segment_badge(segment)
    largest = data.sort_values(["customers", "segment"], ascending=[False, True]).iloc[0]
    intelligence_brief([f"Among the displayed segments, {largest.segment} has the most purchasers ({number(largest.customers)}). Percentages still refer to the full purchaser population."])
    st.dataframe(segment_table(data).style.format({"Customers (%)": "{:.1f}%", "Net value (GBP)": "£{:,.2f}",
        "Orders per purchaser": "{:.2f}", "Average order value (GBP)": "£{:,.2f}"}), hide_index=True, width="stretch")
    chart(px.bar(data.assign(value_gbp=data.net_value_micros / 1e6), x="segment", y="value_gbp",
                 color="segment", color_discrete_map=SEGMENT_COLORS,
                 title="Where is customer value concentrated?", labels={"segment": "RFM segment", "value_gbp": "Net transaction value (GBP)"}).update_layout(showlegend=False))
    chart(px.bar(data, x="segment", y="average_frequency", title="How often do customers in each segment purchase?",
                 color="segment", color_discrete_map=SEGMENT_COLORS,
                 labels={"segment": "RFM segment", "average_frequency": "Orders per purchaser"}).update_layout(showlegend=False))
    st.caption("Segment net value includes signed adjustments for purchasers; return-only customers have no RFM segment.")


def retention_page(load, metadata):
    st.write("Cohorts group customers by month of first observed qualifying purchase. Retention is the percentage of the original cohort purchasing in each later month. Absence of a later purchase does NOT prove customer churn.")
    matrix = load("get_cohort_retention_matrix")
    scope = st.radio("Cohort scope", ["All cohorts", "Choose cohorts"], horizontal=True)
    cohorts = matrix.cohort_month.tolist() if scope == "All cohorts" else st.multiselect("Cohorts to display", matrix.cohort_month.tolist())
    st.caption("Filter scope: heatmap and cohort table only; original cohort denominators and repeat-purchase metrics stay unchanged.")
    visible = matrix[matrix.cohort_month.isin(cohorts)]
    if not visible.empty:
        values = visible.filter(regex=r"^month_\d+$")
        chart(go.Figure(go.Heatmap(z=values.to_numpy(), x=list(range(len(values.columns))), y=pd.to_datetime(visible.cohort_month).dt.strftime("%b %Y"),
            zmin=0, zmax=100, colorscale="Blues", colorbar=dict(title="Retention %"), hoverongaps=False,
            hovertemplate="Cohort %{y}<br>Month %{x}<br>Retention %{z:.1f}%<extra></extra>"
        )).update_layout(title="Are acquired customers coming back?", height=max(380, len(visible) * 23 + 150),
            xaxis_title="Months since first observed purchase", yaxis_title="First observed purchase cohort"))
        with st.expander("View cohort data", expanded=False):
            st.dataframe(visible.style.format({c: "{:.1f}%" for c in values.columns}, na_rep="—"), hide_index=True, width="stretch")
    else:
        st.info("No cohorts selected or no qualifying purchases available.")
    end = metadata["observation_end"]
    if end and not pd.Timestamp(end).is_month_end:
        st.warning(f"{end[:7]} is a partial activity month (observed through {end}). This also affects the final acquisition cohort. Its diagonal cells are incomplete.")
    st.caption("Month 0 is 100%. Blank cells are future/unobserved periods, not zero retention. First observed purchase may follow purchases outside this extract.")
    intelligence_brief([f"{len(visible)} first-observed purchase cohorts are displayed. Future periods remain unobserved; acquisition here means first observed purchase in this extract."])
    st.subheader("Repeat-purchase behaviour")
    repeat = load("get_repeat_purchase_summary").iloc[0]
    k = load("get_customer_kpis").iloc[0]
    cards([
        ("One-time Purchasers", number(repeat.one_time_customers), "Exactly one qualifying order."),
        ("Repeat Purchasers", number(repeat.repeat_customers), "At least two qualifying orders."),
        ("Repeat Purchase Rate", number(repeat.repeat_purchase_rate_pct, 1, "%"), "Repeat purchasers / all purchasers."),
        ("Average Purchase Frequency", number(k.average_purchase_frequency, 2), "Orders per purchaser."),
        ("Median Consecutive-order Interval", number(repeat.median_interval_days, 1, " days"), "All observed consecutive-order gaps, including fractional days."),
        ("Median First-to-second Interval", number(repeat.median_first_second_days, 1, " days"), "Customers with an observed second order only."),
    ])
    distribution = load("get_purchase_frequency_distribution")
    chart(px.bar(distribution, x="purchase_invoices", y="customers", title="How many orders do purchasers place?",
                 labels={"purchase_invoices": "Qualifying purchase orders", "customers": "Purchasers"}))


def customer_page(load):
    customer = st.text_input("Find customer by ID", placeholder="Enter an exact retail customer ID", help="Scope: this customer profile and its transaction history only.").strip()
    if not customer:
        st.info("Select or enter a customer ID to explore their history.")
        return
    result = load("get_customer_profile", customer_key=customer)
    if result.empty:
        st.info("No eligible transaction history found for this customer ID.")
        return
    p = result.iloc[0]
    st.subheader(f"Customer {customer}")
    if pd.notna(p.segment):
        segment_badge(p.segment)
        rfm_scores(p.r_score, p.f_score, p.m_score)
        st.write(f"**{p.segment}** — {EXPLANATIONS[p.segment]}")
        st.caption(f"R score: {int(p.r_score)} · F score: {int(p.f_score)} · M score: {int(p.m_score)}. Descriptive rules, not causal explanations or guaranteed actions.")
    else:
        st.info("Return/adjustment-only customer: no qualifying purchases, RFM scores or acquisition cohort.")
    cards([
        ("Purchase Orders", number(p.frequency), "Distinct qualifying customer/invoice pairs."),
        ("Recency", number(p.recency_days, 0, " days"), "Days since last qualifying purchase at the displayed reference date."),
        ("Average Order Value", number(p.average_order_value_gbp, 2, currency=True), "Gross qualifying purchases / orders."),
        ("Gross Purchase Value", number(p.gross_purchase_micros / 1e6, 2, currency=True), "Qualifying historical purchases."),
        ("Net Ledger Value", number(p.net_value_micros / 1e6, 2, currency=True), "All signed eligible customer transactions."),
        ("Median Order Interval", number(p.median_interval_days, 1, " days"), "Undefined when fewer than two orders are observed."),
    ])
    readable_date = lambda value: pd.Timestamp(value).strftime("%d %b %Y") if pd.notna(value) else "Not available"
    st.write(f"First qualifying purchase: {readable_date(p.first_purchase_date)} · Latest: {readable_date(p.last_purchase_date)}")
    st.write(f"Return / adjustment lines: {int(p.adjustment_lines):,} · Signed adjustment value: {number(p.return_signed_micros / 1e6, 2, currency=True)}")
    st.caption(f"Observed transaction countries: {p.countries or 'Unknown'}. These are transaction attributes, not an inferred residence. Adjustments include positive cancellations and negative non-cancellation lines; no order matching is inferred.")
    activity = load("get_customer_activity", customer_key=customer)
    if len(activity) >= 2:
        activity = activity.assign(month=pd.to_datetime(activity.month).dt.strftime("%b %Y"))
        chart(px.bar(activity, x="month", y="purchase_orders", title="When did this customer place purchase orders?",
                     labels={"month": "Observed purchase month", "purchase_orders": "Qualifying orders"}))
    elif len(activity) == 1:
        st.info(f"Purchases are observed in one month only ({pd.Timestamp(activity.iloc[0].month).strftime('%b %Y')}). More purchase periods are needed to show a trend.")
    st.subheader("Transaction history")
    page_count = max(1, (int(p.eligible_lines) + 49) // 50)
    page = st.number_input("History page", min_value=1, max_value=page_count, value=1, step=1, key=f"history_{customer}")
    history = load("get_customer_history", customer_key=customer, limit=50, offset=(page - 1) * 50)
    history = history.assign(**{"Amount (GBP)": (history.amount_micros / 1e6).round(2)}).drop(columns="amount_micros")
    history = history.rename(columns={"invoice_timestamp": "Transaction time", "invoice": "Invoice", "product_key": "Product code",
        "description": "Representative product description", "quantity": "Quantity", "country_key": "Transaction country", "activity": "Activity"})
    history["Transaction time"] = pd.to_datetime(history["Transaction time"]).dt.strftime("%d %b %Y %H:%M")
    st.caption(f"Page {page} of {page_count} · Up to 50 transaction lines, newest first. Lines are not orders.")
    st.dataframe(history.style.format({"Amount (GBP)": "£{:,.2f}"}, na_rep="—"), hide_index=True, width="stretch")


def show_retail_dashboard(db_path=None, *, view=None):
    """Render a routed view, or retain the standalone selector when omitted.

    ``view`` is keyword-only to match the application router; the positional
    database argument remains supported for fixture and standalone callers.
    """
    apply_design()
    st.caption("InsightFlow AI · Online Retail II · Historical retail transactions. Independent of the Telco churn population.")
    view = view or st.radio("Retail view", VIEWS, horizontal=True)
    if view != "Executive Pulse":
        st.title(view)
    with st.expander("About this analysis"):
        st.write("Online Retail II records historical online retail transactions. Anonymous customer lines are excluded from customer metrics. Qualifying purchases have positive quantity and are not cancellations; orders are distinct customer/invoice pairs. Signed returns and adjustments remain in the net ledger. Duplicate source occurrences are retained.")
        st.write("RFM uses days since last purchase, order count and gross purchase value, with tie-aware relative scores. Segments follow fixed precedence rules. Cohorts use first observed purchase, not confirmed acquisition. Historical value is not a prediction. The extract does not establish causes or prove churn; the final month may be incomplete.")
    path = Path(db_path) if db_path is not None else DATABASE
    try:
        if not path.is_file():
            st.warning("Retail data is not available. Prepare the Online Retail II database using the documented retail ETL, then reopen this view.")
            return
        version = database_version(path)
        def load(name, **kwargs):
            return query(name, str(path.resolve()), version, **kwargs)
        with st.spinner("Loading retail analysis…"):
            metadata = load("get_analysis_metadata")
            st.caption(f"Observation end: {metadata['observation_end'] or 'Not available'} · RFM reference date: {metadata['analysis_date'] or 'Not available'}")
            if metadata["observation_end"] is None:
                st.info("The retail database has no eligible transactions yet.")
                return
            if view == "Executive Pulse":
                overview(load)
            elif view == "Customer Segments":
                segments_page(load)
            elif view == "Retention":
                retention_page(load, metadata)
            else:
                customer_page(load)
    except (OSError, sqlite3.Error, pd.errors.DatabaseError):
        st.error("Retail data could not be read. Check that the local database is available and passes retail ETL validation, then retry.")
