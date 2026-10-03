"""Bounded UI facade for the deterministic InsightFlow knowledge assistant."""
from dataclasses import dataclass
from typing import Callable

from rag.answering import ask as answer_question
from rag.evidence import INSUFFICIENT, PARTIAL, SUPPORTED

REFUSED = "REFUSED"
ERROR = "ERROR"
MAX_QUESTION_LENGTH = 4000


@dataclass(frozen=True)
class AskResult:
    status: str
    answer: str
    evidence: tuple
    reason: str | None = None


class InsightFlowKnowledgeService:
    """Read-only facade. It exposes no ingestion, execution, or mutation method."""

    def __init__(self, answerer: Callable[[str], dict] = answer_question,
                 readiness: Callable[[], bool] | None = None):
        self._answerer = answerer
        self._readiness = readiness

    def ask(self, question):
        if not isinstance(question, str) or not question.strip():
            return AskResult(INSUFFICIENT, "", (), "empty_question")
        question = question.strip()
        if len(question) > MAX_QUESTION_LENGTH:
            return AskResult(REFUSED, "", (), "question_too_long")
        try:
            if self._readiness is not None and not self._readiness():
                return AskResult(ERROR, "", (), "knowledge_base_unavailable")
            raw = self._answerer(question)
            return _validated_result(raw)
        except Exception:
            return AskResult(ERROR, "", (), "service_unavailable")


def _validated_result(raw):
    if not isinstance(raw, dict):
        return AskResult(ERROR, "", (), "malformed_result")
    reason = raw.get("reason")
    if raw.get("abstained"):
        if reason in {"retrieval_unavailable", "evidence_selection_unavailable",
                      "evidence_integrity_failure"}:
            return AskResult(ERROR, "", (), reason)
        status = REFUSED if reason == "unsupported_or_instruction_request" else INSUFFICIENT
        return AskResult(status, "", (), reason or "insufficient_evidence")
    status = raw.get("sufficiency")
    if status not in {SUPPORTED, PARTIAL} or not isinstance(raw.get("answer"), str):
        return AskResult(ERROR, "", (), "malformed_result")
    sources, evidence = raw.get("sources"), raw.get("passages")
    if not isinstance(sources, list) or not isinstance(evidence, list) or not evidence:
        return AskResult(ERROR, "", (), "malformed_result")
    validated = []
    for passage in evidence:
        if not isinstance(passage, dict) or type(passage.get("source_index")) is not int:
            return AskResult(ERROR, "", (), "malformed_result")
        index = passage["source_index"] - 1
        if not 0 <= index < len(sources) or not isinstance(passage.get("text"), str):
            return AskResult(ERROR, "", (), "malformed_result")
        source = sources[index]
        if not all(isinstance(source.get(field), str)
                   for field in ("document", "section", "chunk_id")):
            return AskResult(ERROR, "", (), "malformed_result")
        validated.append({
            "document": source["document"], "section": source["section"],
            "chunk_id": source["chunk_id"], "text": passage["text"],
            "citation": index + 1,
        })
    return AskResult(status, raw["answer"], tuple(validated))
