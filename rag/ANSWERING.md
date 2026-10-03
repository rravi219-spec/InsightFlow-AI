# InsightFlow Knowledge Assistant — evidence-selected local answers

This is a CLI and Python API. There is no Streamlit chatbot, SQL agent, hosted inference, paid API, or API key. Existing SQL, ETL, ML models, and UI behavior are unchanged.

## Root cause and retained design

The first Milestone 6C/6D implementation asked SmolLM2-360M-Instruct to choose request-local evidence IDs with greedy, grammar-constrained decoding. Its prompt contained an illustrative `["E1", "E3"]` output. On the unchanged ten-question answer set, the model returned exactly E1 and E3 for every answerable question. The retrieved candidates were different for each question, so the failure was not caused by the JSON parser, fallback handling, context truncation, or source-level retrieval. It was prompt-example copying and position bias amplified by greedy constrained decoding.

The downloaded model remains documented and ignored under `data/generation_models/`; it was not replaced to hide the result. It is no longer trusted to select evidence or generate factual answer text. The production answer path is deterministic and extractive:

```text
Question → validation/policy gate → hybrid retrieval → freshness/authority filtering
         → evidence-unit extraction → content scoring and redundancy control
         → three-state sufficiency → quoted answer + validated citations
```

LangChain `RunnableLambda` stages still orchestrate the path. Retrieval and embeddings are injectable for tests. No deprecated agent or conversational-chain API is used.

## Evidence selection

`rag/evidence.py` extracts prose sentences, bullets, formulas, and meaningful table rows. It scores their content using the pinned MiniLM embeddings, literal query-term coverage, phrase overlap, bounded document-rank influence, and generic intent features for definitions, denominators, treatment questions, and measured counts. Section text can improve semantic context but cannot satisfy lexical sufficiency. Acronyms cannot masquerade as all requested facets.

Selection is independent of request-local labels. It uses deterministic ordering, suppresses exact/near duplicate units, and applies a redundancy penalty so repeated wording does not crowd out another requested facet. A maximum of three units is emitted. Tests place the same relevant passage at every candidate position, behind misleading high-ranked text, beside multiple relevant passages, and among duplicates.

The selector returns one of:

- `SUPPORTED`: the bounded evidence passes semantic and facet-coverage checks.
- `PARTIALLY_SUPPORTED`: some useful evidence exists, but the requested facets are incomplete.
- `INSUFFICIENT`: evidence is too weak; the assistant abstains.

The thresholds are development-set heuristics, not calibrated probabilities. Quantitative answers additionally require multi-count evidence. RFM support requires all three R/F/M definition units. Unsupported, empty, stale-index, retrieval-failure, and selector-failure paths fail closed.

## Output and citations

`ask(question)` returns `answer`, `sources`, `passages`, `sufficiency`, `abstained`, `mode`, and diagnostics. Every passage must be an exact substring of a retrieved approved chunk. Each citation is mapped to the original document, section, and chunk ID. Application code constructs inline source markers; no model can invent prose or citations.

Insufficient evidence returns exactly:

> I don't have enough evidence in the InsightFlow knowledge base to answer that.

The output is concise extractive synthesis. Exact quotation and citation identity establish provenance, not truth outside the approved documentation.

## Retrieval and freshness

The assistant uses `retrieve_ranked()`: up to 20 dense candidates are reranked with normalized lexical relevance and explicit source authority. RFM, CLV, and documented anonymous-customer terminology are normalized to improve passage recall without embedding expected answer text. Definition questions prefer current methodology; measured count questions prefer dated validation. Historical checkpoints stay indexed for retrieval evaluation but are excluded from answer construction.

Cloud retrieval lazily creates one process-cached, immutable matrix from the current approved documents. Source hashes captured during initialization are rechecked before retrieval, so a mixed stale/current corpus fails closed. A fresh process deterministically reconstructs chunks and vectors without persistent index files. Optional local Chroma build/evaluation remains separate from the production query path.

Queries cannot select files, mutate the index, execute commands, or invoke SQL. Direct prompt-injection patterns, external current-fact requests, and unsupported individual-customer requests abstain before answer construction.

## Historical generation-model record

Ollama was unavailable. The earlier experiment selected HuggingFaceTB/SmolLM2-360M-Instruct at revision `a10cc1512eabd3dde888204e902eca88bddb4951` (about 690 MiB of safetensors weights) for CPU use on the inspected 15.8 GiB Windows machine. Its position-biased evidence-selection result disqualifies it from the trusted answer path. Unit tests and the final evaluator do not require it to run.

Run:

```powershell
python -m rag.ask "How is RFM calculated?"
python -m rag.evaluate_answers
```

The evaluation writes ignored traces to `data/vector_store/answer_evaluation.json`, including ranked chunks, selected passages, sufficiency diagnostics, and citation checks. See `ANSWER_EVALUATION.md` for measured results and limitations.
