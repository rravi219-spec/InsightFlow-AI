"""Run the fixed answer set and retain retrieval/selection traces for review."""
import json
from pathlib import Path
from time import perf_counter

from rag.answering import build_chain
from rag.config import STORE
from rag.ranking import retrieve_ranked


def run_evaluation():
    cases = json.loads(Path(__file__).with_name("answer_evaluation_set.json").read_text(encoding="utf-8"))
    rows = []
    captured = []
    def retrieve(question, k):
        chunks = retrieve_ranked(question, k)
        captured.extend(chunks)
        return chunks
    chain = build_chain(retrieve)
    for case in cases:
        captured.clear()
        start = perf_counter()
        result = chain.invoke(case["question"])
        known = {c["chunk_id"]: c for c in captured}
        valid = all(s["chunk_id"] in known and s["document"] == known[s["chunk_id"]]["source"]
                    and s["section"] == known[s["chunk_id"]]["section"] for s in result["sources"])
        quotes_valid = all(p["text"] in known[result["sources"][p["source_index"] - 1]["chunk_id"]]["text"]
                           for p in result.get("passages", []))
        trace = [{"rank": rank, "source": chunk["source"], "section": chunk["section"],
                  "chunk_id": chunk["chunk_id"], "cosine_similarity": chunk.get("cosine_similarity"),
                  "ranking_score": chunk.get("ranking_score"), "text": chunk["text"]}
                 for rank, chunk in enumerate(captured, 1)]
        rows.append({**case, "result": result, "citation_valid": valid, "quotes_valid": quotes_valid,
                     "seconds": round(perf_counter() - start, 3), "retrieval_trace": trace})
        print(case["id"], "abstained=" + str(result["abstained"]), "reason=" + str(result.get("reason")), flush=True)
        (STORE / "answer_evaluation.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


if __name__ == "__main__":
    run_evaluation()
