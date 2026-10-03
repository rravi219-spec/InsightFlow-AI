"""Immutable in-memory semantic retrieval for the cloud query path."""
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from langchain_core.retrievers import BaseRetriever
from pydantic import PrivateAttr

from rag.chunking import chunk_documents
from rag.config import DIMENSION, MAX_K
from rag.documents import load_documents
from rag.embeddings import LocalEmbeddings


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


@dataclass(frozen=True)
class KnowledgeIndex:
    """Read-only chunks and normalized vectors built from approved documents."""
    chunks: tuple
    vectors: np.ndarray
    source_hashes: tuple
    embeddings: object

    def similarity_search_with_score(self, query, k=5):
        vector = np.asarray(self.embeddings.embed_query(query), dtype=np.float32)
        if vector.shape != (DIMENSION,):
            raise ValueError("Unexpected query embedding dimension")
        norm = np.linalg.norm(vector)
        if norm:
            vector = vector / norm
        similarities = self.vectors @ vector
        order = sorted(range(len(self.chunks)), key=lambda i: (
            -float(similarities[i]), self.chunks[i].metadata["source"],
            self.chunks[i].metadata["chunk_id"],
        ))[:k]
        return [(self.chunks[i], 1.0 - float(similarities[i])) for i in order]

    def similarity_search(self, query, k=5):
        return [document for document, _ in self.similarity_search_with_score(query, k)]


def build_knowledge_index(embeddings=None, documents=None):
    """Build without persistence from the fixed allowlist and deterministic chunker."""
    embeddings = embeddings or local_embeddings()
    documents = tuple(load_documents() if documents is None else documents)
    chunks = tuple(chunk_documents(documents, embeddings.tokenizer))
    if not chunks:
        raise ValueError("Cannot initialize an empty knowledge index")
    vectors = np.asarray(
        embeddings.embed_documents([chunk.page_content for chunk in chunks]),
        dtype=np.float32,
    )
    if vectors.shape != (len(chunks), DIMENSION):
        raise ValueError("Unexpected document embedding dimensions")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.where(norms == 0, 1, norms)
    vectors.setflags(write=False)
    hashes = tuple(sorted((doc.metadata["source"], doc.metadata["source_sha256"])
                          for doc in documents))
    return KnowledgeIndex(chunks, vectors, hashes, embeddings)


@lru_cache(maxsize=1)
def knowledge_index():
    return build_knowledge_index()


def retrieve(query, k=5):
    validate_query(query, k)
    index = knowledge_index()
    return search(index, query, min(k, len(index.chunks)))


def search(store, query, k=5):
    validate_query(query, k)
    return [{"text": doc.page_content, "source": doc.metadata["source"],
             "section": doc.metadata["section"], "chunk_id": doc.metadata["chunk_id"],
             "cosine_distance": float(distance), "cosine_similarity": 1.0 - float(distance)}
            for doc, distance in store.similarity_search_with_score(query.strip(), k=k)]
