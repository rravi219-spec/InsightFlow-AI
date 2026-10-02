# Grounded-answer quality hardening — 2026-10-01

The fixed development sets were retained. Results below are actual local runs with the pinned MiniLM embeddings and the current 115-chunk index. Generated traces remain ignored under `data/vector_store/`.

## Root-cause reproduction

Before hardening, all ten answerable questions produced the exact model selection `{"evidence":["E1","E3"]}`, even though their ranked passages differed. The prompt itself demonstrated E1/E3 and the 360M model used greedy finite-grammar decoding. The model copied the example/positions. Parsing succeeded, no fallback ran, and inputs fit the context limit. Source retrieval was healthy. The defect was evidence-selection position bias, not citation mapping.

The previous manual result was:

- 6/10 complete
- 1/10 partial
- 3/10 insufficient
- 10/10 citation identities and quotations valid
- 4/4 out-of-scope abstentions
- 5/5 direct prompt-injection abstentions

## Hardened selection and sufficiency

The trusted path now scores extracted evidence content rather than asking the local model to emit evidence labels. It preserves semantic scoring, literal facet coverage, phrase overlap, source rank, generic definition/denominator/treatment/count cues, duplicate suppression, and deterministic redundancy control. Section labels can help embedding context but cannot satisfy lexical coverage. A maximum of three exact units is returned.

Three explicit states replace the previous binary behavior: `SUPPORTED`, `PARTIALLY_SUPPORTED`, and `INSUFFICIENT`. Insufficient evidence abstains. Partial evidence is labeled as partial. Thresholds are development heuristics and are exposed in diagnostics; they are not probabilities.

Position tests put a relevant passage in each of five candidate positions and verify the same content wins. Additional tests cover multiple relevant passages, no relevant passage, misleading high-ranked text, near duplicates, partial support, retrieval/selector failures, freshness, authority, citation structure, and injection handling.

## Retrieval quality

The unchanged ten-question source-document benchmark produced:

| Method | Hit@1 | Hit@3 | Hit@5 |
|---|---:|---:|---:|
| Original dense retrieval | 70% | 90% | 100% |
| Hybrid reranking used by answers | 100% | 100% | 100% |

The benchmark is source-level. It does not prove the selected sentence answers the question, which is why answer selection is measured separately.

## Grounded-answer evaluation

Manual review used the unchanged criteria in `answer_evaluation_set.json`. Criteria never enter runtime selection.

| Topic | Result | Evidence selected |
|---|---|---|
| RFM | Complete / supported | Recency, frequency, and monetary definitions |
| Cohort retention | Complete / supported | First observed month, active/original formula, future NULL meaning |
| Repeat purchase | Complete / supported | At least two invoices and all behavioral customers denominator |
| Historical value vs CLV | Complete / supported | Explicit historical-not-predicted distinction |
| Observed vs predicted churn | Complete / supported | Source observed label and model probability |
| ETL fact grain | Complete / supported | `fact_transaction` and `(source_sheet, source_row)` |
| Anonymous customers | Complete / supported | No invented identity; excluded from customer metrics |
| Returns/cancellations | Complete / supported | Excluded from qualifying purchases; signed adjustments in net value |
| TotalCharges | Complete / supported | Blank to NULL without imputation; malformed nonblank blocks ingestion |
| Dataset scale | Complete / supported | 1,067,371 staging/raw rows and 1,061,163 fact rows |

Final manual result: **10/10 complete and supported**. Some answers remain mechanically phrased because they quote formulas or Markdown table rows. The selector is intentionally extractive and may include a low-value third unit on novel paraphrases; this small development set is not a held-out generalization result.

All **10/10** substantive responses had valid document/section/chunk citations, and every emitted passage was an exact substring of its cited retrieved chunk.

## Abstention and injection

All **4/4** out-of-scope cases abstained: current stock price, weather, unsupported individual-customer data, and an invented metric. All **5/5** direct injection attempts abstained: ignore grounding, reveal prompt, fabricate a metric, override source boundaries, and execute a command.

The runtime exposes no shell, SQL, filesystem, or vector-store mutation tool. These tests cover declared attacks, not every possible paraphrase.

## Reproducibility and release assessment

Run:

```powershell
python -m rag.evaluate
python -m rag.evaluate_answers
python -m unittest discover -s tests -v
python -m compileall analytics etl frontend ml backend rag
python -m pip check
git diff --check
```

The evaluator records complete retrieval order, scores, text, selected passages, sufficiency diagnostics, citations, and timings. Evaluation artifacts are ignored.

The assistant is suitable for a constrained local Streamlit pilot only if the UI exposes citations and the `PARTIALLY_SUPPORTED`/`INSUFFICIENT` states without hiding them. It is not validated for unrestricted production questions. The development set is small, thresholds were tuned on it, answers are extractive, and prompt-injection pattern guards cannot prove protection against unseen attacks.
