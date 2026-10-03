# Ask InsightFlow

Ask InsightFlow is a constrained documentation assistant integrated into the existing Streamlit navigation. It answers questions about approved InsightFlow analytics, ETL, data quality, retail customer analytics, and implementation methodology. It is not an autonomous agent, SQL agent, web-search assistant, or production support system.

## Architecture

    Streamlit page
    -> read-only rag.service facade
    -> existing validation and policy gates
    -> hybrid retrieval and freshness checks
    -> deterministic evidence selection
    -> sufficiency classification
    -> grounded answer and exact citations

The page does not contain retrieval, ranking, or safety rules. `InsightFlowKnowledgeService.ask(question)` returns a structured immutable result with status, answer, validated evidence, citations, and a bounded reason code. The facade fails closed if the result or citation mapping is malformed.

The Ask module is lightweight: it imports the RAG service only after a question is submitted. The first question lazily loads the pinned public MiniLM revision, reads exactly the eight approved tracked documents, deterministically chunks them, computes a normalized in-memory embedding matrix, and caches that resource for later questions in the process. It does not create a vector database or write an index. A local pre-downloaded model is reused when available; a clean cloud runtime downloads only the pinned revision through SentenceTransformers. Provisioning failures produce a bounded operational state without exposing paths or a stack trace, and do not affect unrelated pages.

## Visible states

- **SUPPORTED:** display the grounded answer and supporting evidence.
- **PARTIALLY_SUPPORTED:** warn that documentation supports only part of the response.
- **INSUFFICIENT:** explain that indexed documentation lacks enough evidence.
- **REFUSED / OUT OF SCOPE:** explain the approved-documentation boundary.
- **Operational error:** report unavailable local resources without a stack trace or sensitive path.

Substantive answers include an expandable **View supporting evidence** area. Every entry uses the answer's actual citation number and shows its relative source document, section, exact supporting passage, and chunk ID. Retrieved Markdown is rendered with safe Streamlit primitives rather than unsafe HTML.

Questions are limited to 4,000 characters. Example questions come from the evaluation scope. History exists only in Streamlit session state and is never written to a database, file, index, or telemetry service.

## Security and limitations

The facade exposes only `ask`. It has no shell, SQL, filesystem-selection, database-mutation, ingestion, Git, network, Python-execution, or index-mutation method. Existing out-of-scope, injection, source allowlist, freshness, and citation checks remain authoritative.

The assistant is a constrained pilot. Its evaluation set is small, sufficiency thresholds are development heuristics, answers are extractive, and unseen injection paraphrases remain possible. A new application process rebuilds the small in-memory corpus from tracked sources; it does not rely on persistent cloud storage. It is not validated for unrestricted production use.
