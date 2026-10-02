"""Heading-aware deterministic chunks using LangChain's token length splitter."""
import hashlib
import json

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from rag.config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_documents(documents, tokenizer):
    headers = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")], strip_headers=False)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        length_function=lambda text: len(tokenizer.encode(text, add_special_tokens=False, verbose=False)),
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = []
    for doc in documents:
        index = 0
        for section in headers.split_text(doc.page_content):
            heading = " > ".join(section.metadata[k] for k in ("h1", "h2", "h3") if k in section.metadata) or "Introduction"
            for content in splitter.split_text(section.page_content):
                if len(tokenizer.encode(content, add_special_tokens=False, verbose=False)) > CHUNK_SIZE:
                    raise ValueError("Chunk exceeds the embedding token budget")
                identity = json.dumps([doc.metadata["source"], heading, index, content], ensure_ascii=False)
                metadata = {**doc.metadata, "section": heading, "chunk_index": index,
                            "chunk_id": hashlib.sha256(identity.encode()).hexdigest()}
                chunks.append(Document(page_content=content, metadata=metadata))
                index += 1
    return chunks
