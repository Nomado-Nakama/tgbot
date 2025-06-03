import torch, os

import asyncio
from functools import cache
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from sentence_transformers import SentenceTransformer

torch.set_num_threads(4)
os.environ["OMP_NUM_THREADS"] = "4"

_EXECUTOR = ThreadPoolExecutor(max_workers=4)

_model_singleton: SentenceTransformer | None = None


def warm_up():
    global _model_singleton
    _model_singleton = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    _model_singleton.encode("warm-up")  # first real forward-pass


asyncio.get_event_loop().run_in_executor(None, warm_up)  # fire-and-forget


async def generate_embedding(text: str) -> list[float]:
    loop = asyncio.get_running_loop()
    emb: np.ndarray = await loop.run_in_executor(
        _EXECUTOR, lambda: _model_singleton().encode(text, normalize_embeddings=True)
    )
    return emb.astype(float).tolist()
