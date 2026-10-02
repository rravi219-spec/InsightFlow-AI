# Local retrieval evaluation — 2026-10-01

This is a retrieval-infrastructure evaluation, not a completed RAG system or answer-quality evaluation. No LLM was used. The ten questions and expected source documents in `evaluation_set.json` were defined before the first retrieval run and were not broadened after observing misses.

## Configuration and results

- Eight approved Markdown documents; **114 chunks**.
- MiniLM model/revision and token splitting are pinned in `config.py`; 384-dimensional normalized embeddings, cosine distance, no reranker.
- Largest observed chunk: **220 WordPiece tokens**.
- **Hit@1: 7/10 (70%)**.
- **Hit@3: 9/10 (90%)**.
- **Hit@5: 10/10 (100%)**.

| Question topic | Hit@1 | Hit@3 | Hit@5 |
|---|---|---|---|
| RFM definitions | No | Yes | Yes |
| Cohort retention | No | Yes | Yes |
| Repeat-purchase definition | Yes | Yes | Yes |
| Historical value versus predicted lifetime value | Yes | Yes | Yes |
| Observed versus predicted churn | Yes | Yes | Yes |
| ETL fact grain | Yes | Yes | Yes |
| Anonymous customers | No | No | Yes |
| Returns and cancellations | Yes | Yes | Yes |
| TotalCharges handling | Yes | Yes | Yes |
| Dataset scale | Yes | Yes | Yes |

Hit means an expected **source document**, not necessarily a sufficient passage, appears among the first k chunks. Multiple chunks from a single document consume ranking positions. No expected prose answers or answer scores were defined.

## Manual passage inspection

Several retrieved passages were read directly after the run:

- **RFM:** rank 1 was `analytics/RETAIL_CUSTOMER_VALIDATION.md`, section “RFM methodology and actual distribution,” cosine similarity **0.564**. It correctly describes R/F/M and the reference date, but is not the predeclared expected methodology document. The expected `analytics/RETAIL_CUSTOMER_ANALYTICS.md` appeared at rank 2 (**0.466**) and explicitly defines all three metrics. This is a source-label miss at rank 1 despite relevant content.
- **TotalCharges:** rank 1 was `analytics/README.md`, “Data-quality checks,” **0.526**. The passage directly states blank charges are SQL NULL without imputation and malformed/negative/non-finite nonblank values block ingestion. This is a relevant passage as well as a source hit.
- **Fact grain:** rank 1 was `etl/README.md`, “Grain, keys and relationships,” **0.571**. The passage discusses dimension keys and required/nullable fact attributes, but does not itself fully state the composite fact primary key. The source hit overstates passage completeness.
- **Historical value versus predicted lifetime value:** rank 1 was `frontend/RETAIL_DASHBOARD.md`, “Caching and local performance,” **0.445**. This is the expected document but an irrelevant passage about query latency. It counts as Hit@1 under the requested metric; it is not evidence that the question is answered.
- **Anonymous customers:** rank 1 was `analytics/RETAIL_CUSTOMER_VALIDATION.md`, “Scope and populations,” **0.574**. It mentions no fabricated identities and qualifying known customers, but the predeclared expected document appears only at rank 4. That rank-4 passage concerns value concentration and does not directly resolve the question. Again, source-level Hit@5 does not guarantee relevant context.

These examples show why no broad retrieval-quality claim follows from 100% source Hit@5. The small set is a development smoke evaluation, not a held-out benchmark; expected-source choices and duplicate topics across documents affect scores. Chunk-level labels, larger paraphrase/adversarial sets and potentially reranking need separate evaluation before an answer-generating milestone.

## Reproducibility and safety validation

A second explicit real-model build ran with Python socket connections blocked. It produced identical chunk IDs and exactly equal stored vectors (maximum absolute difference **0.0**) on this local environment. Offline retrieval also passed. A mutation-shaped query left collection documents and metadata unchanged. This does not promise bit-identical floating-point results across different hardware/library versions.

All **88 tests passed**: 74 prior tests plus 14 focused retrieval tests. Tests cover allowlist rejection, redirected/missing sources, secret-pattern rejection, deterministic IDs, metadata, token limits, explicit rebuilds, failed-build recovery, real temporary Chroma retrieval, LangChain retriever integration, query/k limits, no implicit index creation, query non-mutation and evaluation calculations. Compilation, pip dependency check and Git whitespace checks passed.

Generated full results, passage text, source hashes and offline verification evidence remain ignored under `data/vector_store/`. Only this measured summary and the manually authored question set belong in source control. Nothing was committed, pushed, merged or deployed as part of this milestone.
