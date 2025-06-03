from src.bot.embeddings import generate_embedding
from src.bot.qdrant_client import client, QDRANT_COLLECTION
from src.bot.content_dao import get_content
from qdrant_client.http.models import SearchRequest


async def search_content(query: str, top_k: int = 3):
    vector = await generate_embedding(query)
    hits = await client.search(
        collection_name=QDRANT_COLLECTION,
        search_request=SearchRequest(vector=vector, limit=top_k, with_payload=True),
    )
    for hit in hits:
        item = await get_content(int(hit.id))
        if item:
            yield item, hit.score
