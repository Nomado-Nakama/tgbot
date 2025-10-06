from __future__ import annotations

from loguru import logger

from src.config import settings

from src.content.models import SyncStats
from src.content.sync.storage import repository
from src.content.parser import parse_lines_to_nodes
from src.content.sync.sources.google_docs import fetch_document



async def _walk_and_upsert(parent_id: int | None, node, ord_idx: int, force_reembed: bool, out_seen: set[int],
                           out_embeds: list[tuple[int, str, str, bool]], stats: SyncStats) -> int:
    cid, need_emb, is_new, updated_changed = await repository.upsert_node(
        parent_id=parent_id,
        ord_=ord_idx,
        title=node.title,
        body=node.body,
        force_reembed_all=force_reembed,
    )

    if is_new:
        stats.inserted += 1
    if updated_changed:
        stats.updated += 1

    # Prepare embeddings payload when needed
    if need_emb:
        text = (node.body or node.title or "")
        out_embeds.append((cid, text, node.title, bool(node.body)))

    out_seen.add(cid)

    for i, child in enumerate(node.children):
        await _walk_and_upsert(cid, child, i, force_reembed, out_seen, out_embeds, stats)

    return cid


async def run_once(force_reembed_all_if_empty: bool = True) -> SyncStats:
    """
    Orchestrates: fetch → rev check → early rev write → parse → db upsert → delete missing → embed+upsert.
    Returns SyncStats for observability.
    """
    stats = SyncStats()

    # 1) figure out doc_id from settings URL
    doc_id = settings.FULL_CONTENT_GOOGLE_DOCS_URL.split("/")[-1]

    # 2) fetch doc
    raw, new_rev = fetch_document(doc_id)

    # 3) decide if we need a sync (and whether we force re-embed due to empty collection)
    prev_rev = await repository.get_doc_revision()

    force_reembed = False
    if settings.ENABLE_VECTOR_SEARCH and force_reembed_all_if_empty:
        from src.content.sync.vectorstore.qdrant_store import is_collection_empty
        if await is_collection_empty():
            logger.warning("🆕 Empty Qdrant collection detected – forcing full re-index")
            prev_rev = "totally_nonexistent_revision"
            force_reembed = True

    if new_rev == prev_rev:
        logger.info("🟢 Google Doc revision unchanged – skipping synchronisation.")
        return stats

    # 4) early update the revision to avoid infinite loops on crashes
    await repository.set_doc_revision(new_rev)

    # 5) parse into nodes
    nodes = parse_lines_to_nodes(raw)
    logger.info(f"✅ Parsed — {len(nodes)} top-level nodes")

    # 6) upsert all nodes; collect candidates for embedding
    seen_ids: set[int] = set()
    embed_candidates: list[tuple[int, str, str, bool]] = []

    for idx, root in enumerate(nodes):
        await _walk_and_upsert(None, root, idx, force_reembed, seen_ids, embed_candidates, stats)

    # 7) delete rows that disappeared + delete their vectors
    all_ids = set(await repository.list_all_content_ids())
    to_delete = list(all_ids - seen_ids)
    if to_delete:
        await repository.delete_content_ids(to_delete)
        if settings.ENABLE_VECTOR_SEARCH:
            from src.content.sync.vectorstore.qdrant_store import delete_points
            await delete_points(to_delete)
        stats.deleted += len(to_delete)
        logger.info(f"🗑️  Deleted {len(to_delete)} obsolete rows and vectors")

    # 8) embed + upsert to Qdrant
    if settings.ENABLE_VECTOR_SEARCH and embed_candidates:
        from qdrant_client.http.models import PointStruct
        from src.tools.embeddings import generate_embeddings
        from src.tools.qdrant_high_level_client import QDRANT_COLLECTION
        from src.content.sync.vectorstore.qdrant_store import upsert_points

        texts = [t for (_cid, t, _title, _has_body) in embed_candidates]
        vectors = generate_embeddings(texts)
        points = [
            PointStruct(id=cid, vector=[float(x) for x in vec], payload={"title": title, "has_body": has_body})
            for (cid, _txt, title, has_body), vec in zip(embed_candidates, vectors)
        ]
        await upsert_points(points)
        stats.embedded += len(points)
        logger.success(f"✅ Upserted {len(points)} vectors into {QDRANT_COLLECTION}")
    elif not settings.ENABLE_VECTOR_SEARCH:
        logger.info("Skipping embedding generation and Qdrant upsert (vector search disabled).")
    elif not embed_candidates:
        logger.success("🟢 No content changes that require new embeddings.")

    return stats
