"""Explicit Chroma builds, atomically published via a small manifest."""
import json
import os
from pathlib import Path
from uuid import uuid4

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma

from rag.config import STORE, MODEL_NAME, MODEL_REVISION, DIMENSION, CHUNK_SIZE, CHUNK_OVERLAP, SOURCES


def client(path):
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False, allow_reset=False))


def build_store(chunks, embeddings, path=STORE, *, rebuild=False):
    path = Path(path)
    manifest_path = path / "manifest.json"
    if manifest_path.exists() and not rebuild:
        raise FileExistsError("Index already exists; use --rebuild explicitly")
    if not chunks:
        raise ValueError("Cannot publish an empty index")
    if any(c.metadata.get("source") not in SOURCES for c in chunks):
        raise ValueError("Unapproved chunk source")
    name = "insightflow-" + uuid4().hex
    store = Chroma(client=client(path), collection_name=name, embedding_function=embeddings,
                   collection_metadata={"hnsw:space": "cosine"})
    try:
        for offset in range(0, len(chunks), 128):
            batch = chunks[offset:offset + 128]
            store.add_documents(batch, ids=[c.metadata["chunk_id"] for c in batch])
        if store._collection.count() != len(chunks):
            raise ValueError("Stored chunk count does not reconcile")
        manifest = {"schema_version": 1, "collection": name, "model": MODEL_NAME, "revision": MODEL_REVISION,
            "dimension": DIMENSION, "chunk_size_tokens": CHUNK_SIZE, "overlap_tokens": CHUNK_OVERLAP,
            "chunks": len(chunks), "sources": {c.metadata["source"]: c.metadata["source_sha256"] for c in chunks}}
        temporary = path / (name + ".json")
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.replace(temporary, manifest_path)
        return manifest
    except Exception:
        store.delete_collection()
        raise


def open_store(embeddings, path=STORE):
    path = Path(path)
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Documentation index missing; run python -m rag.build_index")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("model"), manifest.get("revision"), manifest.get("dimension")) != (MODEL_NAME, MODEL_REVISION, DIMENSION):
        raise ValueError("Embedding configuration changed; rebuild the index explicitly")
    if not set(manifest["sources"]).issubset(SOURCES):
        raise ValueError("Index contains unapproved sources")
    store = Chroma(client=client(path), collection_name=manifest["collection"], embedding_function=embeddings,
                   create_collection_if_not_exists=False)
    return store, manifest
