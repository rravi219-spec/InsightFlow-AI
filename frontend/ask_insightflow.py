"""Constrained Streamlit presentation for the read-only RAG service."""
import streamlit as st

SUPPORTED = "SUPPORTED"
PARTIAL = "PARTIALLY_SUPPORTED"
INSUFFICIENT = "INSUFFICIENT"
REFUSED = "REFUSED"
ERROR = "ERROR"
MAX_QUESTION_LENGTH = 4000

EXAMPLES = (
    "What do the RFM metrics mean?",
    "How is TotalCharges handled?",
    "How are retail returns treated?",
    "How is customer retention calculated?",
)


@st.cache_resource
def knowledge_service():
    """Import the RAG stack only after a user submits a question."""
    from rag.service import InsightFlowKnowledgeService
    return InsightFlowKnowledgeService()


def response_view(result):
    """Pure page-state mapping used by the renderer and tests."""
    if result.status == SUPPORTED:
        return "success", "Supported by InsightFlow documentation", result.answer
    if result.status == PARTIAL:
        return ("warning", "Partially supported",
                result.answer or "The available documentation supports only part of this question.")
    if result.status == REFUSED:
        return ("warning", "Outside the supported scope",
                "Ask InsightFlow only answers questions grounded in approved project documentation.")
    if result.status == INSUFFICIENT:
        return ("info", "Insufficient documented evidence",
                "The indexed InsightFlow documentation does not contain enough evidence to answer this question.")
    return ("error", "Knowledge assistant unavailable",
            "The local knowledge base could not answer this request. Check that its index and embedding model are available.")


def _render_result(result):
    level, label, message = response_view(result)
    getattr(st, level)(label)
    st.write(message)
    if result.evidence:
        with st.expander("View supporting evidence"):
            for number, item in enumerate(result.evidence, 1):
                st.markdown(f"**[{item['citation']}] {item['document']}**")
                if item["section"]:
                    st.caption(item["section"])
                st.write(item["text"])
                st.caption(f"Chunk: {item['chunk_id']}")
                if number < len(result.evidence):
                    st.divider()


def show_ask_insightflow(service=None):
    st.title("Ask InsightFlow")
    st.write("Ask questions about InsightFlow's documented analytics, ETL, data quality, "
             "customer analytics and implementation methodology.")
    st.caption("Answers are grounded only in approved InsightFlow documentation. "
               "This assistant cannot search the web, query customer databases, or execute actions.")

    if "ask_insightflow_question" not in st.session_state:
        st.session_state.ask_insightflow_question = ""
    if "ask_insightflow_history" not in st.session_state:
        st.session_state.ask_insightflow_history = []

    st.markdown("#### Example questions")
    for column, example in zip(st.columns(4), EXAMPLES):
        if column.button(example, key="ask_example_" + str(EXAMPLES.index(example))):
            st.session_state.ask_insightflow_question = example

    question = st.text_input(
        "Question",
        key="ask_insightflow_question",
        max_chars=MAX_QUESTION_LENGTH,
        placeholder="Ask about documented InsightFlow methodology or validation...",
    )
    if st.button("Ask", type="primary", key="ask_insightflow_submit"):
        if not question.strip():
            st.warning("Enter a question before asking InsightFlow.")
        else:
            with st.spinner("Reviewing approved documentation..."):
                result = (service or knowledge_service()).ask(question)
            st.session_state.ask_insightflow_history.append((question, result))

    if st.session_state.ask_insightflow_history:
        question, result = st.session_state.ask_insightflow_history[-1]
        st.markdown(f"### {question}")
        _render_result(result)
        if len(st.session_state.ask_insightflow_history) > 1:
            with st.expander("Session history"):
                for previous_question, previous_result in reversed(
                        st.session_state.ask_insightflow_history[:-1]):
                    st.markdown(f"**{previous_question}**")
                    st.caption(response_view(previous_result)[1])
