"""Explicit local documentation build: python -m rag.build_index [--rebuild]."""
import argparse
import json

from rag.documents import load_documents
from rag.chunking import chunk_documents
from rag.embeddings import LocalEmbeddings, download_model
from rag.vector_store import build_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--download-model", action="store_true", help="Explicitly download the pinned public model")
    args = parser.parse_args()
    documents = load_documents()
    if args.download_model:
        download_model()
    embeddings = LocalEmbeddings()
    chunks = chunk_documents(documents, embeddings.tokenizer)
    print(json.dumps(build_store(chunks, embeddings, rebuild=args.rebuild), indent=2))


if __name__ == "__main__":
    main()
