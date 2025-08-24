from __future__ import annotations

from typing import Iterable, List

from loguru import logger
from qdrant_client.http.models import PointStruct, PointIdsList

from src.tools.qdrant_high_level_client import client, QDRANT_COLLECTION, ensure_collection


async def is_collection_empty() -> bool:
    """
    Robust check: try scroll(1); fallback to count().
    Keeps compatibility with your previous tuple-based scroll usage.
    """
    try:
        result = await client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=None,
            with_payload=False,
            limit=1,
        )
        # Previous code treated scroll result as tuple(points, next_page_offset)
        if isinstance(result, tuple):
            points, _ = result
            return len(points) == 0
        # Newer clients may return object with "points" attr
        points = getattr(result, "points", [])
        return len(points) == 0
    except Exception:
        try:
            cnt = await client.count(collection_name=QDRANT_COLLECTION)
            # Some clients return int, others return object with .count
            value = getattr(cnt, "count", cnt)
            return int(value or 0) == 0
        except Exception as e:
            logger.warning(f"Failed to check Qdrant emptiness: {e}")
            return False  # don't force if unsure


async def upsert_points(points: List[PointStruct]) -> None:
    await client.upsert(collection_name=QDRANT_COLLECTION, points=points)


async def delete_points(ids: Iterable[int]) -> None:
    await client.delete(collection_name=QDRANT_COLLECTION, points_selector=PointIdsList(points=list(ids)))
