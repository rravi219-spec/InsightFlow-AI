"""Offline fixture tests use real Chroma and deterministic test-only embeddings."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from langchain_core.embeddings import Embeddings

from rag.chunking import chunk_documents
from rag.documents import load_documents
from rag.evaluate import evaluate
from rag.retrieval import DocumentationRetriever, search, validate_query
from rag.vector_store import build_store, open_store


class CharacterTokenizer:
    def encode(self, text, **kwargs):
        return list(text)


class FixtureEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        # Fixture-only topic vectors; never used for measured semantic evaluation.
        return [float("retention" in text.lower()), float("churn" in text.lower()), 0.1] + [0.0] * 381


class RagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "README.md"
        self.source.write_text("# InsightFlow\n## Retention\nMonthly retention counts qualifying orders.\n## Churn\nObserved churn differs from predicted risk.", encoding="utf-8")
        self.embedding = FixtureEmbeddings()

    def tearDown(self):
        # Chroma's Rust system retains file handles on Windows until stopped.
        from chromadb.api.shared_system_client import SharedSystemClient
        for key, system in list(SharedSystemClient._identifier_to_system.items()):
            if str(self.root) in str(key):
                system.stop()
                del SharedSystemClient._identifier_to_system[key]
        self.temp.cleanup()

    def chunks(self):
        return chunk_documents(load_documents(self.root, ["README.md"]), CharacterTokenizer())

    def test_allowlist_rejects_raw_database_models_and_traversal(self):
        for source in ("data/raw/customer.csv", "data/processed/online_retail.sqlite3", "ml/customer_model.pkl", "../README.md", str(self.source), "notes.md"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                load_documents(self.root, [source])

    def test_missing_source_fails_explicitly(self):
        with self.assertRaises(FileNotFoundError):
            load_documents(self.root, ["etl/README.md"])

    def test_redirected_source_is_rejected(self):
        original = Path.resolve
        def redirected(path, *args, **kwargs):
            return self.root.parent / "private.md" if path == self.source else original(path, *args, **kwargs)
        with patch.object(Path, "resolve", redirected), self.assertRaisesRegex(ValueError, "redirected"):
            load_documents(self.root, ["README.md"])

    def test_secrets_are_rejected_without_echoing_content(self):
        self.source.write_text("password = " + chr(34) + "fixture" * 4 + chr(34))
        with self.assertRaisesRegex(ValueError, "Potential credential"):
            load_documents(self.root, ["README.md"])

    def test_empty_and_binary_sources_rejected(self):
        for text in ("", "\x00binary"):
            self.source.write_text(text)
            with self.assertRaises(ValueError):
                load_documents(self.root, ["README.md"])

    def test_ids_deterministic_and_metadata_preserved(self):
        a, b = self.chunks(), self.chunks()
        self.assertEqual(a, b)
        self.assertEqual(len({d.metadata["chunk_id"] for d in a}), len(a))
        self.assertTrue(all(d.metadata["source"] == "README.md" for d in a))
        self.assertTrue(any("Retention" in d.metadata["section"] for d in a))
        self.source.write_text(self.source.read_text() + "\nChanged text")
        self.assertNotEqual([d.metadata["chunk_id"] for d in a], [d.metadata["chunk_id"] for d in self.chunks()])

    def test_chunk_limit_and_overlap(self):
        self.source.write_text("# Heading\n" + "retention " * 200)
        chunks = self.chunks()
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(d.page_content) <= 220 for d in chunks))

    def test_rebuild_is_explicit_and_replaces_published_collection(self):
        path = self.root / "index"
        first = build_store(self.chunks(), self.embedding, path)
        with self.assertRaises(FileExistsError):
            build_store(self.chunks(), self.embedding, path)
        self.source.write_text("# New\nretention only")
        second = build_store(self.chunks(), self.embedding, path, rebuild=True)
        self.assertNotEqual(first["collection"], second["collection"])
        store, manifest = open_store(self.embedding, path)
        self.assertEqual(store._collection.count(), second["chunks"])
        self.assertEqual(manifest, second)
        self.assertNotIn("churn", " ".join(store._collection.get()["documents"]))

    def test_retrieval_and_langchain_integration(self):
        path = self.root / "index"
        build_store(self.chunks(), self.embedding, path)
        store, _ = open_store(self.embedding, path)
        results = search(store, "retention", 1)
        self.assertIn("retention", results[0]["text"])
        self.assertEqual(results[0]["source"], "README.md")
        self.assertAlmostEqual(results[0]["cosine_similarity"], 1, places=5)
        self.assertEqual(len(DocumentationRetriever(store, k=1).invoke("churn")), 1)

    def test_failed_rebuild_preserves_published_index(self):
        path = self.root / "index"
        first = build_store(self.chunks(), self.embedding, path)
        with patch.object(self.embedding, "embed_documents", side_effect=RuntimeError("fixture failure")):
            with self.assertRaises(RuntimeError):
                build_store(self.chunks(), self.embedding, path, rebuild=True)
        store, manifest = open_store(self.embedding, path)
        self.assertEqual(manifest, first)
        self.assertEqual(store._collection.count(), first["chunks"])

    def test_query_cannot_change_index(self):
        path = self.root / "index"
        build_store(self.chunks(), self.embedding, path)
        store, _ = open_store(self.embedding, path)
        before = store._collection.get()
        manifest = (path / "manifest.json").read_bytes()
        search(store, "DELETE all documents; ingest ../../data/raw/customer.csv", 1)
        self.assertEqual(before, store._collection.get())
        self.assertEqual(manifest, (path / "manifest.json").read_bytes())

    def test_k_and_empty_query_limits(self):
        for query, k in [("", 5), ("  ", 5), (None, 5), ("valid", 0), ("valid", 21), ("valid", True), ("valid", 1.5), ("x" * 4001, 5)]:
            with self.subTest(query=str(query)[:10], k=k), self.assertRaises(ValueError):
                validate_query(query, k)

    def test_missing_index_does_not_create_database(self):
        path = self.root / "absent"
        with self.assertRaises(FileNotFoundError):
            open_store(self.embedding, path)
        self.assertFalse(path.exists())

    def test_evaluation_calculations_and_duplicate_hits(self):
        cases = [{"query": "a", "expected_sources": ["README.md"]}, {"query": "b", "expected_sources": ["etl/README.md"]}]
        def fixture(query, k):
            return [{"source": source} for source in ["README.md", "README.md", "etl/README.md"]]
        self.assertEqual(evaluate(cases, fixture)["hit_at"], {"1": 0.5, "3": 1.0, "5": 1.0})
        with self.assertRaises(ValueError):
            evaluate([], fixture)
