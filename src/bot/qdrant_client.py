from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams
from src.bot.config import settings

QDRANT_COLLECTION = "content_vectors"
_VECTOR_SIZE = 384

client = AsyncQdrantClient(url=settings.QDRANT_URL)


async def ensure_collection():
    await client.recreate_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
    )
