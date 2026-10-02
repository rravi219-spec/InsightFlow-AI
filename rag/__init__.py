"""Local documentation retrieval only; no answer generation or SQL agent."""
import os

# This package intentionally does not emit hosted LangSmith traces.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
