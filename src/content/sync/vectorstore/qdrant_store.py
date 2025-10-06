from typing import Iterable, List, Any
from loguru import logger
from src.config import settings

if settings.ENABLE_VECTOR_SEARCH:
    from qdrant_client.http.models import PointStruct, PointIdsList
    from src.tools.qdrant_high_level_client import client, QDRANT_COLLECTION

    async def is_collection_empty() -> bool:
        try:
            result = await client.scroll(
                collection_name=QDRANT_COLLECTION,
                scroll_filter=None,
                with_payload=False,
                limit=1,
            )
            if isinstance(result, tuple):
                points, _ = result
                return len(points) == 0
            points = getattr(result, "points", [])
            return len(points) == 0
        except Exception:
            try:
                cnt = await client.count(collection_name=QDRANT_COLLECTION)
                value = getattr(cnt, "count", cnt)
                return int(value or 0) == 0
            except Exception as e:
                logger.warning(f"Failed to check Qdrant emptiness: {e}")
                return False

    async def upsert_points(points: List["PointStruct"]) -> None:
        await client.upsert(collection_name=QDRANT_COLLECTION, points=points)

    async def delete_points(ids: Iterable[int]) -> None:
        await client.delete(collection_name=QDRANT_COLLECTION, points_selector=PointIdsList(points=list(ids)))
else:
    # Safe no-ops when vector search is disabled
    async def is_collection_empty() -> bool:
        return False

    async def upsert_points(points: List[Any]) -> None:
        return None

    async def delete_points(ids: Iterable[int]) -> None:
        return None