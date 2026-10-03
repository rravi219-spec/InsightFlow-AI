# Local documentation retrieval and grounded answers

Milestone 6A/6B provides local retrieval. Milestone 6C/6D adds a [local extractive Knowledge Assistant](ANSWERING.md): deterministic content scoring selects evidence units, which are returned with validated citations and an explicit sufficiency state. The earlier small-model selector is retained only as a documented failed experiment because it exhibited position bias. There is no Streamlit chatbot, SQL agent, hosted inference, or unrestricted free-form answer generation.

The [Ask InsightFlow Streamlit pilot](../frontend/ASK_INSIGHTFLOW.md) calls the
same hardened pipeline through a read-only service facade. The page adds no
retrieval rules, execution tools, ingestion behavior, or persistent chat
storage.

```text
Approved documents → heading-aware chunks → pinned CPU embeddings → cached in-memory vectors → semantic retrieval
```

## Cloud runtime and optional local tooling

From the repository root, using the existing Python environment:

```powershell
python -m pip install -r requirements.txt
python -m rag.evaluate
```

The trusted Streamlit/CLI query path lazily downloads the pinned public embedding revision when no local model snapshot exists, builds an immutable in-memory matrix from tracked documentation, and caches it for the process. No API key, hosted model, persistent index, or generation model is required. `requirements.txt` is the single cloud dependency manifest.

Persistent Chroma remains optional local development/evaluation tooling. Install its separate environment and explicitly provision a local snapshot/index with:

```powershell
python -m pip install -r requirements-rag.txt
python -m rag.build_index --download-model --rebuild
```

## Source boundary

Exactly eight paths are approved in `config.SOURCES`: `README.md`, `analytics/README.md`, `analytics/RETAIL_CUSTOMER_ANALYTICS.md`, `analytics/RETAIL_CUSTOMER_VALIDATION.md`, `etl/README.md`, `etl/VALIDATION.md`, `frontend/RETAIL_DASHBOARD.md`, and `docs/MILESTONE_CHECKPOINT.md`.

The loader never discovers files or follows document links. Missing, empty, binary, oversized, redirected/symlinked or unapproved sources fail explicitly. No raw dataset, database, model pickle or transaction export is loaded. A conservative credential-pattern check rejects suspicious documentation; this is not a comprehensive secret detector. Approved documents must remain reviewed documentation rather than becoming a place to paste private records. Aggregate historical validation figures and documented customer-ID examples are documentation, not raw-record ingestion. Earlier checkpoint documents describe their historical milestone, which can differ from the current UI.

## Chunk and embedding contract

LangChain `Document` objects preserve relative source path, normalized source SHA-256, heading hierarchy, chunk position and SHA-256 chunk ID. Markdown headings are retained in text. Recursive splitting uses the pinned model's WordPiece tokenizer: **220 tokens maximum, 40 tokens overlap target**, within a section. Splits favor paragraphs, lines and words; overlap may be smaller near boundaries. IDs hash source, section, position and exact chunk text. No filesystem timestamps or random values enter chunk IDs.

Model: [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, **384 dimensions**, normalized vectors, CPU, batch size 32. The Apache-2.0 model has approximately 22.7 million parameters and is intended for short English paragraphs/semantic search. It was chosen for a small local footprint, not an unmeasured claim of domain accuracy. Its default input limit is 256 word pieces; long queries can be truncated by the encoder. Source chunks stay below that limit.

The safetensors weights are roughly 90 MB; PyTorch and the dependency environment require substantially more disk/RAM. A CPU is sufficient; no GPU is required. Budget several GB of free disk/RAM for installation and execution rather than treating weight size as process memory. No production throughput or minimum-memory claim is made. The runtime uses safetensors and `trust_remote_code=False`. It reuses an ignored `data/embedding_models/<revision>/` snapshot when present; otherwise it requests the exact pinned Hugging Face revision and uses the normal library cache.

## Production retrieval and local Chroma

Production retrieval stores normalized chunk vectors in a read-only NumPy matrix. The matrix, chunks, source hashes, and embedding model are initialized only by the first query and reused in the process. Query vectors use cosine similarity with deterministic source/chunk tie-breaking. No user query can add documents, choose paths, write an index, or rebuild the corpus.

The optional local Chroma builder uses ignored `data/vector_store/`, cosine distance and a manifest containing model revision, chunk parameters, source hashes and chunk count. It is retained for persistence tests and historical evaluation; Streamlit does not import or open it. A failed local build keeps the published collection, and explicit rebuilds may leave old generated collections for safety.

```python
from rag.retrieval import retrieve
results = retrieve("How is repeat purchase rate defined?", k=5)
```

Each result contains `text`, `source`, `section`, `chunk_id`, `cosine_distance` (smaller is closer) and `cosine_similarity = 1 - distance` (larger is closer). Similarity is not a probability or calibrated confidence. `k` must be an integer 1–20; fewer results are possible when the corpus is smaller. Empty queries and queries over 4,000 characters are rejected. Query text is embedded as data, never interpreted as SQL, a command, a file path or an ingestion request. Retrieval exposes no mutation tools.

For LangChain orchestration without answer generation, `DocumentationRetriever(index, k=5).invoke(query)` returns LangChain documents from an explicitly initialized in-memory resource. The public `retrieve()` API additionally exposes cosine distances. The default model and knowledge resource are reused in-process; they are not a remote service.

## Evaluation and tests

`evaluation_set.json` is a manually authored ten-question set with expected source documents, not expected prose answers. It was written before running retrieval. `python -m rag.evaluate` measures Hit@1/3/5: whether any expected document occurs among the first k **chunks**. Multiple chunks from one document consume multiple positions; they do not count as multiple hits. Results include retrieved text for manual semantic inspection. This small document-level check does not establish chunk-level answer completeness, robustness to arbitrary questions, or answer accuracy.

Unit tests use fixture documentation, deterministic test-only vectors and actual temporary Chroma persistence; they do not download models. Real semantic measurements use the actual pinned SentenceTransformers model separately. Run:

```powershell
python -m unittest discover -s tests -v
python -m compileall analytics etl frontend ml backend rag
python -m pip check
git diff --check
```

Integration reference: [LangChain Chroma documentation](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma). Measured results and manual examples will be recorded separately in `EVALUATION.md`; no quality result is implied by successful index creation.
