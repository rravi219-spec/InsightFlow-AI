"""Goal-oriented navigation, with legacy Telco views grouped under Predictive AI."""
import streamlit as st
import streamlit_option_menu

GROUPS = {
    "OVERVIEW": ["Executive Pulse"],
    "CUSTOMER INTELLIGENCE": ["Customer Segments", "Retention", "Customer 360"],
    "PREDICTIVE AI": ["Churn Intelligence", "AI Insights"],
    "KNOWLEDGE": ["Ask InsightFlow"],
    "ANALYTICS": ["Reports", "Settings"],
}


def navigation():
    st.markdown("**INSIGHTFLOW AI**")
    st.caption("Customer Intelligence & Analytics Platform")
    group = st.radio("Workspace", list(GROUPS), label_visibility="collapsed")
    return streamlit_option_menu.option_menu(None, GROUPS[group], default_index=0, key=f"navigation_{group}", styles={
        "container": {"padding": "5px", "background-color": "#0d1629"},
        "nav-link": {"font-size": "15px", "text-align": "left", "margin": "5px", "color": "#c6d4e8", "--hover-color": "#1d2e49"},
        "nav-link-selected": {"background-color": "#2456a6", "color": "#ffffff"},
        "icon": {"color": "#80b4ff"},
    })
