from loguru import logger
from src.config import settings
from src.bot.content_dao import get_content


async def search_content(query: str, top_k: int = 2):
    if not settings.ENABLE_VECTOR_SEARCH:
        logger.info("Vector search disabled; skipping semantic search.")
        return  # async generator with no results

    # Heavy imports only when needed
    from src.tools.embeddings import generate_embedding
    from src.tools.qdrant_high_level_client import client, QDRANT_COLLECTION

    logger.info(f"Creating embedding for query: {query}")
    vector = await generate_embedding(query)
    logger.info(f"Got vector with {len(vector)} dimensions for query: {query}")
    hits = await client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=vector,
        limit=top_k,
        search_params={"hnsw_ef": 256},
    )

    for hit in hits:
        item = await get_content(int(hit.id))
        logger.info(f"item: {item} for hit_id: {hit.id} for query: {query}")
        if item:
            yield item, hit.score