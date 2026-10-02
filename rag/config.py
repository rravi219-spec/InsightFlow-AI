from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "README.md", "analytics/README.md", "analytics/RETAIL_CUSTOMER_ANALYTICS.md",
    "analytics/RETAIL_CUSTOMER_VALIDATION.md", "etl/README.md", "etl/VALIDATION.md",
    "frontend/RETAIL_DASHBOARD.md", "docs/MILESTONE_CHECKPOINT.md",
)
STORE = ROOT / "data/vector_store"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_PATH = ROOT / "data/embedding_models" / MODEL_REVISION
DIMENSION = 384
CHUNK_SIZE = 220  # WordPiece tokens, below the model's 256-token limit.
CHUNK_OVERLAP = 40
MAX_K = 20
