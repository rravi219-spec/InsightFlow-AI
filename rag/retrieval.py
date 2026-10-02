"""Semantic search results only. Queries cannot choose paths or mutate collections."""
from functools import lru_cache

from langchain_core.retrievers import BaseRetriever
from pydantic import PrivateAttr

from rag.config import STORE, MAX_K
from rag.embeddings import LocalEmbeddings
from rag.vector_store import open_store


def validate_query(query, k):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be nonempty text")
    if len(query) > 4000:
        raise ValueError("Query exceeds 4000 characters")
    if type(k) is not int or not 1 <= k <= MAX_K:
        raise ValueError(f"k must be an integer from 1 to {MAX_K}")


class DocumentationRetriever(BaseRetriever):
    k: int = 5
    _store: object = PrivateAttr()

    def __init__(self, store, k=5):
        validate_query("validation", k)
        super().__init__(k=k)
        self._store = store

    def _get_relevant_documents(self, query, *, run_manager):
        validate_query(query, self.k)
        return self._store.similarity_search(query, k=self.k)


@lru_cache(maxsize=1)
def local_embeddings():
    return LocalEmbeddings()


def retrieve(query, k=5):
    validate_query(query, k)
    # Check existence before loading a model or opening Chroma; no implicit index build.
    if not (STORE / "manifest.json").is_file():
        raise FileNotFoundError("Documentation index missing; run python -m rag.build_index")
    store, manifest = open_store(local_embeddings())
    return search(store, query, min(k, manifest["chunks"]))


def search(store, query, k=5):
    validate_query(query, k)
    return [{"text": doc.page_content, "source": doc.metadata["source"],
             "section": doc.metadata["section"], "chunk_id": doc.metadata["chunk_id"],
             "cosine_distance": float(distance), "cosine_similarity": 1.0 - float(distance)}
            for doc, distance in store.similarity_search_with_score(query.strip(), k=k)]
