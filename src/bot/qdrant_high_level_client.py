import asyncio

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams

from src.bot.config import settings

QDRANT_COLLECTION = "content_vectors"
_VECTOR_SIZE = 384

client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT,
                           prefer_grpc=True, timeout=30, **{"check_compatibility": False})


async def ensure_collection():
    logger.info("Ensuring Qdrant collection...")
    for attempt in range(15):
        try:
            info = await client.info()
            break
        except Exception as exc:
            logger.warning(f"Qdrant not ready ({exc}), retrying…")
            await asyncio.sleep(2)
    else:
        raise RuntimeError("Qdrant never became ready")

    logger.info(f"Qdrant info: {info}...")
    if not await client.collection_exists(collection_name=QDRANT_COLLECTION):
        logger.info(f"creating fresh QDRANT_COLLECTION: {QDRANT_COLLECTION}...")
        await client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
    else:
        logger.info(f"QDRANT_COLLECTION: {QDRANT_COLLECTION} exists...")
        await client.delete_collection(
            collection_name=QDRANT_COLLECTION
        )
        await client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
