"""Fail-closed grounded answers orchestrated with LangChain runnables."""
import re

from langchain_core.runnables import RunnableLambda

from rag.config import SOURCES
from rag.evidence import INSUFFICIENT, PARTIAL, select_evidence
from rag.ranking import METHODOLOGY, MEASUREMENTS, measured_question, retrieve_ranked, tokens
from rag.retrieval import validate_query

ABSTENTION = "I don't have enough evidence in the InsightFlow knowledge base to answer that."
INJECTION = re.compile(
    r"ignore.{0,60}(instruction|rule|ground|previous)|"
    r"(reveal|print|show|repeat|disclose).{0,40}(system prompt|hidden instruction)|"
    r"(invent|fabricate|make up).{0,40}(metric|fact|number|citation)|"
    r"(override|bypass).{0,50}(source|restrict|rule|ground)|"
    r"(execute|run).{0,30}(command|shell|powershell|python|sql)|"
    r"\b(system|assistant)\s*:|<\|(?:im_start|system)", re.I | re.S)
OUTSIDE = re.compile(r"\b(weather|stock price|share price|today's price|current price)\b|"
                     r"\bcustomer\s+(?:id\s*)?[#:]?\s*\d+\b", re.I)
def refused(reason):
    return {"answer": ABSTENTION, "sources": [], "abstained": True, "reason": reason,
            "sufficiency": INSUFFICIENT, "mode": "deterministic_extractive"}


def prepare(question, retriever):
    try:
        validate_query(question, 5)
    except ValueError:
        return {"result": refused("invalid_question")}
    if INJECTION.search(question) or OUTSIDE.search(question):
        return {"result": refused("unsupported_or_instruction_request")}
    try:
        chunks = retriever(question, k=20)
    except Exception:
        return {"result": refused("retrieval_unavailable")}
    chunks = [c for c in chunks if c.get("source") in SOURCES and c.get("cosine_similarity", 0) >= .25
              and not INJECTION.search(c.get("text", ""))]
    # Do not let old checkpoints compete with current definitions in generation.
    if not measured_question(question) and any(c["source"] in METHODOLOGY for c in chunks):
        chunks = [c for c in chunks if c["source"] not in MEASUREMENTS]
    chunks = [c for c in chunks if c["source"] != "docs/MILESTONE_CHECKPOINT.md"]
    if not chunks:
        return {"result": refused("insufficient_context")}
    query_terms = set(tokens(question)) - {"insightflow", "project", "calculated", "calculate", "defined", "definition", "mean", "does"}
    context_terms = set(tokens(" ".join(c["text"] for c in chunks)))
    if len(query_terms - context_terms) >= 2 and len(query_terms & context_terms) / max(1, len(query_terms)) < .6:
        return {"result": refused("unsupported_question_terms")}
    return {"question": question.strip(), "chunks": chunks}


def choose(state, embeddings=None):
    if "result" in state:
        return state
    try:
        selection = select_evidence(state["question"], state["chunks"], embeddings=embeddings)
        if selection["status"] == INSUFFICIENT:
            return {"result": {**refused("insufficient_evidence"), "diagnostics": _diagnostics(selection)}}
        return {**state, "selection": selection}
    except Exception:
        return {"result": refused("evidence_selection_unavailable")}


def _diagnostics(selection):
    return {"candidate_count": selection["candidate_count"],
            "top_semantic_score": round(selection["top_semantic_score"], 6),
            "query_term_coverage": round(selection["coverage"], 6)}

def _render_unit(text):
    """Turn an evidence unit into a concise clause while retaining verbatim support separately."""
    text = text.strip()
    if text.startswith("|") and text.endswith("|") and "\n" not in text:
        cells = [cell.strip().strip(chr(96)) for cell in text.strip("|").split("|")]
        text = f"{cells[0]}: " + "; ".join(cells[1:])
    text = re.sub(r"^(?:[-*]|\d+\.)\s+", "", text)
    text = text.replace("**", "").replace(chr(96), "")
    return " ".join(text.split())


def construct_answer(state):
    if "result" in state:
        return state["result"]
    selection = state["selection"]
    sources, passages = [], []
    for item in selection["selected"]:
        chunk = item["chunk"]
        if item["text"] not in chunk["text"]:
            return refused("evidence_integrity_failure")
        citation = {"document": chunk["source"], "section": chunk["section"], "chunk_id": chunk["chunk_id"]}
        if citation not in sources:
            sources.append(citation)
        passages.append({"text": item["text"], "source_index": sources.index(citation) + 1,
                         "semantic_score": round(item["semantic_score"], 6)})
    prefix = "The knowledge base provides partial evidence: " if selection["status"] == PARTIAL else ""
    answer = prefix + "; ".join(f"{_render_unit(p['text'])} [{p['source_index']}]"
                                 for p in passages)
    return {"answer": answer, "sources": sources, "passages": passages, "abstained": False,
            "sufficiency": selection["status"], "mode": "deterministic_extractive",
            "diagnostics": _diagnostics(selection)}


def build_chain(retriever=retrieve_ranked, embeddings=None):
    return (RunnableLambda(lambda question: prepare(question, retriever))
            | RunnableLambda(lambda state: choose(state, embeddings))
            | RunnableLambda(construct_answer))


def ask(question):
    return build_chain().invoke(question)
