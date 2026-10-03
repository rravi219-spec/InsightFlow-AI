"""Hybrid ranking and explicit document authority; no question-specific answers."""
from collections import Counter
import math
import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from rag.config import SOURCES
from rag.documents import load_documents
from rag.retrieval import knowledge_index, search, validate_query

METHODOLOGY = {"analytics/README.md", "analytics/RETAIL_CUSTOMER_ANALYTICS.md", "etl/README.md"}
MEASUREMENTS = {"analytics/RETAIL_CUSTOMER_VALIDATION.md", "etl/VALIDATION.md"}


def normalize(text):
    text = text.casefold()
    for short, full in {"rfm": "recency frequency monetary", "clv": "customer lifetime value"}.items():
        text = re.sub(r"\b" + short + r"\b", short + " " + full, text)
    text = re.sub(r"\banonymous\b", "anonymous missing customer null customer key identity", text)
    return text


def tokens(text):
    return [word[:-1] if word.endswith("s") and len(word) > 4 else word
            for word in re.findall(r"[a-z0-9]+", normalize(text)) if word not in ENGLISH_STOP_WORDS]


def measured_question(query):
    return bool(re.search(r"\b(how many|scale|measured|dataset size|validation results|raw rows|fact rows)\b", query.casefold()))


def source_kind(source):
    if source in METHODOLOGY:
        return "current methodology"
    if source in MEASUREMENTS:
        return "dated measurement"
    if source == "docs/MILESTONE_CHECKPOINT.md":
        return "historical checkpoint"
    return "current product documentation"


def rank_candidates(query, candidates):
    query_terms = set(tokens(query))
    documents = [tokens(c["section"] + " " + c["text"]) for c in candidates]
    frequencies = [Counter(words) for words in documents]
    average_length = sum(map(len, documents)) / max(1, len(documents))
    n = len(documents)
    lexical = []
    for words, counts in zip(documents, frequencies):
        score = 0.0
        for term in query_terms:
            df = sum(term in f for f in frequencies)
            idf = math.log(1 + (n - df + .5) / (df + .5))
            tf = counts[term]
            score += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * len(words) / max(average_length, 1)))
        lexical.append(score)
    maximum = max(lexical, default=0) or 1
    ranked = []
    for candidate, bm25 in zip(candidates, lexical):
        source = candidate["source"]
        priority = .15 if source in (MEASUREMENTS if measured_question(query) else METHODOLOGY) else 0
        if source == "docs/MILESTONE_CHECKPOINT.md":
            priority -= .04
        score = .85 * candidate["cosine_similarity"] + .15 * bm25 / maximum + priority
        ranked.append({**candidate, "ranking_score": score, "source_kind": source_kind(source)})
    return sorted(ranked, key=lambda c: (-c["ranking_score"], c["source"], c["chunk_id"]))


def retrieve_ranked(query, k=5):
    validate_query(query, k)
    index = knowledge_index()
    current = {d.metadata["source"]: d.metadata["source_sha256"] for d in load_documents()}
    if tuple(sorted(current.items())) != index.source_hashes:
        raise ValueError("Documentation changed during cached knowledge initialization")
    # Re-rank the full bounded local pool: source-level hits can otherwise
    # hide the specific passage needed for a multi-part answer.
    candidates = search(index, normalize(query), min(20, len(index.chunks)))
    if any(c["source"] not in SOURCES for c in candidates):
        raise ValueError("Unapproved source in retrieval results")
    return rank_candidates(query, candidates)[:k]
