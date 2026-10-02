"""Shared executive presentation components; no analytics calculations."""
from html import escape

import streamlit as st

SEGMENT_COLORS = {
    "Champions": "#34d399", "Loyal": "#60a5fa",
    "Potential Loyalists": "#a78bfa", "New Customers": "#38bdf8",
    "At Risk": "#fbbf24", "Hibernating": "#fb7185",
}


def apply_design():
    st.markdown("""<style>
    .stApp {background:#080f1f;color:#e5edf9;}
    [data-testid="stHeader"] {background:rgba(8,15,31,.96);}
    [data-testid="stSidebar"] {background:#0d1629;border-right:1px solid #23324d;}
    .block-container {max-width:1480px;padding-top:2.5rem;padding-bottom:3rem;}
    h1,h2,h3 {letter-spacing:-.025em;color:#f1f5ff;}
    .insightflow-page-header {margin-bottom:1.5rem;}
    .insightflow-page-title {color:#f1f5ff;font-size:2.15rem;font-weight:750;line-height:1.15;margin:0;}
    .insightflow-page-subtitle {color:#a9b8ce;font-size:1rem;margin:.55rem 0 0;max-width:850px;}
    .risk-card {background:#122139;border:1px solid #2b3f5e;border-radius:16px;min-height:138px;padding:1.2rem;}
    .risk-label {color:#b9c8dd;font-size:.9rem;font-weight:600;}
    .risk-value {color:#f1f5ff;font-size:1.8rem;font-weight:750;margin:.35rem 0;}
    .risk-caption {color:#a9b8ce;font-size:.85rem;}
    [data-testid="stCaptionContainer"] {color:#a9b8ce;font-size:.92rem;}
    .if-hero {padding:2.4rem;border:1px solid #2b4269;border-radius:22px;
      background:linear-gradient(120deg,#142644,#101a31 70%,#211b3c);margin-bottom:1.8rem;}
    .if-eyebrow {color:#80b4ff;font-size:.78rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;}
    .if-hero h1 {font-size:clamp(2rem,4vw,3.6rem);line-height:1.12;margin:.8rem 0;max-width:850px;}
    .if-hero p {color:#c1cee2;font-size:1.1rem;line-height:1.7;}
    .if-capability {border:1px solid #283c5b;border-radius:16px;background:#101d33;padding:1.5rem;height:100%;}
    .if-capability h3 {font-size:1.15rem;margin:.6rem 0;}
    .if-capability p {color:#afbed3;line-height:1.6;}
    div[data-testid="stMetric"] {background:linear-gradient(140deg,#15243b,#101a2c);
      border:1px solid #2b3d58;border-top:3px solid #5797ff;border-radius:16px;padding:1.2rem;min-height:145px;}
    div[data-testid="stMetricValue"] {color:#f1f5ff;font-size:clamp(1.45rem,2.3vw,2.3rem);font-weight:750;}
    div[data-testid="stMetricLabel"] {color:#b9c8dd;}
    [data-testid="stVerticalBlockBorderWrapper"] {border-color:#283954;border-radius:16px;}
    .if-brief {background:linear-gradient(110deg,#181e38,#111d31);border:1px solid #514575;
      border-left:3px solid #a78bfa;border-radius:16px;padding:1.35rem 1.6rem;margin:1.2rem 0 1.7rem;}
    .if-brief h3 {color:#c4b5fd;font-size:1.05rem;margin:0 0 .8rem;}
    .if-brief li {color:#d4def0;margin:.55rem 0;line-height:1.6;}
    .if-badge {display:inline-block;border:1px solid var(--accent);color:var(--accent);
      padding:.3rem .7rem;border-radius:30px;font-size:.88rem;font-weight:650;margin:.3rem .4rem .6rem 0;}
    .if-score {padding:1rem;background:#122139;border-radius:12px;border:1px solid #2b3f5e;}
    .if-score strong {color:#c9d7eb;} .if-dots {display:flex;gap:8px;margin:.85rem 0;}
    .if-dot {height:8px;flex:1;border-radius:4px;background:#33435c;}
    .if-dot.active {background:#8bafff;}
    [data-testid="stExpander"] {background:#101a2c;border-radius:12px;}
    @media(max-width:700px) {.if-hero {padding:1.35rem;} .block-container {padding:1rem;}
      div[data-testid="stMetricValue"] {font-size:1.7rem;} .if-brief {padding:1rem;}}
    </style>""", unsafe_allow_html=True)


def hero():
    st.markdown("""<section class="if-hero">
    <div class="if-eyebrow">InsightFlow AI · Executive Pulse</div>
    <h1>Customer Intelligence<br>Command Center</h1>
    <p>Understand behaviour. Predict risk. Discover customer value.</p>
    <div class="if-eyebrow">Customer Intelligence &amp; Analytics Platform</div>
    </section>""", unsafe_allow_html=True)
    for col, title, detail in zip(st.columns(2), ("Customer Analytics", "Churn Intelligence"), (
        "SQL · RFM · Cohorts · Retention — explore observed retail behaviour and historical customer value.",
        "Machine Learning · Risk Scoring · SHAP — explore the separate Telco population through Predictive AI.",
    )):
        with col:
            st.markdown(f'<div class="if-capability"><div class="if-eyebrow">Platform capability</div><h3>{title}</h3><p>{detail}</p></div>', unsafe_allow_html=True)


def metric_cards(items):
    for start in range(0, len(items), 3):
        for column, (label, value, context) in zip(st.columns(3), items[start:start + 3]):
            with column:
                st.metric(label, value, help=context)
                st.caption(context)


def intelligence_brief(observations):
    if observations:
        items = "".join(f"<li>{escape(str(text))}</li>" for text in observations)
        st.markdown(f'<aside class="if-brief"><h3>✦ Intelligence Brief</h3><ul>{items}</ul></aside>', unsafe_allow_html=True)
        st.caption("Deterministic observations from validated analytics. No generated advice or causal inference.")


def segment_badge(segment):
    color = SEGMENT_COLORS.get(segment, "#a9b8ce")
    st.markdown(f'<span class="if-badge" style="--accent:{color}">{escape(str(segment))}</span>', unsafe_allow_html=True)


def rfm_scores(recency, frequency, monetary):
    for column, label, score in zip(st.columns(3), ("Recency", "Frequency", "Monetary"), (recency, frequency, monetary)):
        score = int(score)
        dots = "".join(f'<span class="if-dot{" active" if i < score else ""}"></span>' for i in range(5))
        with column:
            st.markdown(f'<div class="if-score" role="img" aria-label="{label} score {score} out of 5"><strong>{label}</strong><div class="if-dots">{dots}</div>{score} / 5</div>', unsafe_allow_html=True)


def chart(fig):
    fig.update_layout(template="plotly_dark", paper_bgcolor="#101a2c", plot_bgcolor="#101a2c",
        colorway=["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#fb7185"],
        margin=dict(l=15, r=15, t=70, b=30), font=dict(size=13, color="#c6d4e8"),
        title=dict(font=dict(size=18)), hoverlabel=dict(bgcolor="#1a2c48"))
    with st.container(border=True):
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
