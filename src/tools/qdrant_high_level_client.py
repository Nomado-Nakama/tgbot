import asyncio
from typing import Mapping, Union

from loguru import logger
from src.config import settings

QDRANT_COLLECTION = "content_vectors"
_VECTOR_SIZE = 384

if settings.ENABLE_VECTOR_SEARCH:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http.models import Distance, VectorParams, CollectionInfo

    client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT,
                               prefer_grpc=True, timeout=30, **{"check_compatibility": False})

    def _extract_vector_params(col_info: "CollectionInfo") -> "VectorParams | None":
        try:
            cfg: Union[VectorParams, Mapping[str, VectorParams]] = (
                col_info.config.params.vectors  # type: ignore[attr-defined]
            )
        except AttributeError:
            return None
        if isinstance(cfg, VectorParams):
            return cfg
        if "" in cfg:
            return cfg[""]
        return next(iter(cfg.values()), None)

    def _params_match(vec: "VectorParams | None") -> bool:
        return vec is not None and vec.size == _VECTOR_SIZE and vec.distance == Distance.COSINE

    async def ensure_collection():
        logger.info("Ensuring Qdrant collection...")
        logger.info("📡 Waiting for Qdrant …")
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
            logger.info(f"Collection absent – creating fresh one: {QDRANT_COLLECTION}...")
            await client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )
            return

        col_info = await client.get_collection(collection_name=QDRANT_COLLECTION)
        vec_params = _extract_vector_params(col_info)

        if _params_match(vec_params):
            logger.info(
                "🟢 Qdrant collection is compatible "
                f"(size={vec_params.size}, distance={vec_params.distance}) – keeping data",
            )
            return

        logger.warning(
            "⚠️  Vector params mismatch "
            f"(have size={getattr(vec_params, 'size', None)}, "
            f"distance={getattr(vec_params, 'distance', None)}) – "
            "dropping & recreating collection",
        )

        await client.delete_collection(collection_name=QDRANT_COLLECTION)
        await client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.success("✅ Collection recreated with correct schema")
else:
    client = None  # type: ignore[assignment]

    async def ensure_collection():
        logger.info("Vector search disabled – skipping Qdrant initialization.")
        return