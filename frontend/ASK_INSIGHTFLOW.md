# Ask InsightFlow

Ask InsightFlow is a constrained, local documentation assistant integrated into the existing Streamlit navigation. It answers questions about approved InsightFlow analytics, ETL, data quality, retail customer analytics, and implementation methodology. It is not an autonomous agent, SQL agent, web-search assistant, or production support system.

## Architecture

    Streamlit page
    -> read-only rag.service facade
    -> existing validation and policy gates
    -> hybrid retrieval and freshness checks
    -> deterministic evidence selection
    -> sufficiency classification
    -> grounded answer and exact citations

The page does not contain retrieval, ranking, or safety rules. `InsightFlowKnowledgeService.ask(question)` returns a structured immutable result with status, answer, validated evidence, citations, and a bounded reason code. The facade fails closed if the result or citation mapping is malformed.

The existing embedding loader is process-cached. Streamlit caches only the stateless service facade. Reruns do not rebuild or ingest the index. If the manifest or pinned local embedding model is missing, the page displays an operational error and leaves rebuilding as an explicit developer action:

    python -m rag.build_index --rebuild
    streamlit run frontend/adaptive_dashboard.py

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

The assistant is a constrained local pilot. Its evaluation set is small, sufficiency thresholds are development heuristics, answers are extractive, and unseen injection paraphrases remain possible. Documentation edits require an explicit index rebuild. It is not validated for unrestricted production use.
