import asyncio
from functools import cache
from concurrent.futures import ThreadPoolExecutor

from sentence_transformers import SentenceTransformer
import numpy as np

_EXECUTOR = ThreadPoolExecutor(max_workers=4)


@cache
def _model() -> SentenceTransformer:
    return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


async def generate_embedding(text: str) -> list[float]:
    loop = asyncio.get_running_loop()
    emb: np.ndarray = await loop.run_in_executor(
        _EXECUTOR, lambda: _model().encode(text, normalize_embeddings=True)
    )
    return emb.astype(float).tolist()
