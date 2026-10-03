"""Pinned CPU embeddings with local-first, lazy cloud provisioning."""
import os

from langchain_core.embeddings import Embeddings

from rag.config import MODEL_NAME, MODEL_REVISION, MODEL_PATH, DIMENSION


def download_model():
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL_NAME, revision=MODEL_REVISION, local_dir=str(MODEL_PATH), token=False,
        allow_patterns=["*.json", "vocab.txt", "model.safetensors", "1_Pooling/config.json"],
        ignore_patterns=["onnx/*", "openvino/*"])


class LocalEmbeddings(Embeddings):
    def __init__(self):
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        from sentence_transformers import SentenceTransformer
        local = (MODEL_PATH / "model.safetensors").is_file()
        source = str(MODEL_PATH) if local else MODEL_NAME
        options = {
            "device": "cpu", "local_files_only": local, "trust_remote_code": False,
            "model_kwargs": {"use_safetensors": True},
        }
        if not local:
            # Never follow a moving model branch in cloud deployments.
            options["revision"] = MODEL_REVISION
        self.model = SentenceTransformer(source, **options)
        if self.model.get_embedding_dimension() != DIMENSION:
            raise ValueError("Unexpected embedding dimension")
        self.tokenizer = self.model.tokenizer

    def embed_documents(self, texts):
        return self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False).tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]
