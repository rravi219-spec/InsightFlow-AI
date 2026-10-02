"""Exact allowlist ingestion; never follow links or discover files recursively."""
import hashlib
from pathlib import Path
import re

from langchain_core.documents import Document

from rag.config import ROOT, SOURCES

SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16})|"
    r'''(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*["'][^"'\s]{12,}["']''', re.I)


def load_documents(root=ROOT, sources=SOURCES):
    root = Path(root).resolve()
    sources = tuple(sources)
    if not sources or len(set(sources)) != len(sources) or any(s not in SOURCES for s in sources):
        raise ValueError("Only unique approved documentation paths may be ingested")
    documents = []
    for source in sources:
        path = root / source
        if path.resolve() != path.absolute() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Linked or redirected source rejected: {source}")
        if not path.is_file():
            raise FileNotFoundError(f"Approved source missing: {source}")
        if path.stat().st_size > 2_000_000:
            raise ValueError(f"Documentation size limit exceeded: {source}")
        content = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        if not content.strip() or "\x00" in content:
            raise ValueError(f"Empty or binary documentation: {source}")
        if SECRET.search(content):
            raise ValueError(f"Potential credential found in approved source: {source}")
        documents.append(Document(page_content=content, metadata={
            "source": source, "source_sha256": hashlib.sha256(content.encode()).hexdigest(),
        }))
    return documents
