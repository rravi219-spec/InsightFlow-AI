"""Source-document Hit@k, independent of any language model."""
import json
from pathlib import Path

from rag.config import SOURCES
from rag.retrieval import retrieve


def evaluate(cases, search=retrieve):
    if not cases:
        raise ValueError("Evaluation set must not be empty")
    totals = {1: 0, 3: 0, 5: 0}
    rows = []
    for case in cases:
        expected = set(case["expected_sources"])
        if not expected or not expected.issubset(SOURCES):
            raise ValueError("Evaluation sources must be approved documents")
        results = search(case["query"], k=5)
        hits = {k: any(r["source"] in expected for r in results[:k]) for k in totals}
        for k, hit in hits.items():
            totals[k] += int(hit)
        rows.append({**case, "hits": hits, "results": results})
    return {"questions": len(cases), "hit_at": {str(k): value / len(cases) for k, value in totals.items()}, "cases": rows}


if __name__ == "__main__":
    cases = json.loads(Path(__file__).with_name("evaluation_set.json").read_text(encoding="utf-8"))
    print(json.dumps(evaluate(cases), indent=2, ensure_ascii=False))
