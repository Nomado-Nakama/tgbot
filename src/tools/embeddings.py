import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

from src.config import settings

# Public API: generate_embedding(s) — implementation depends on feature flag

if settings.ENABLE_VECTOR_SEARCH:
    import torch
    from sentence_transformers import SentenceTransformer

    # ─── runtime limits ────────────────────────────────────────────────
    torch.set_num_threads(4)
    os.environ["OMP_NUM_THREADS"] = "4"

    _EXECUTOR = ThreadPoolExecutor(max_workers=4)
    _MODEL = SentenceTransformer(
        "intfloat/multilingual-e5-small",
        backend="onnx",
        device="cpu",
    )
    _MODEL.encode("warm-up")

    async def generate_embedding(text: str) -> list[float]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _EXECUTOR, lambda: _MODEL.encode(text, normalize_embeddings=True)
        )

    def generate_embeddings(texts: list[str], batch_size: int = 256) -> list[list[float]]:
        """Synchronous helper for bulk ingestion."""
        return _MODEL.encode(
            texts, batch_size=batch_size, normalize_embeddings=True
        ).astype(float).tolist()
else:
    async def generate_embedding(text: str) -> list[float]:
        raise RuntimeError("Vector search is disabled (ENABLE_VECTOR_SEARCH=false).")

    def generate_embeddings(texts: list[str], batch_size: int = 256) -> list[list[float]]:
        raise RuntimeError("Vector search is disabled (ENABLE_VECTOR_SEARCH=false).")
