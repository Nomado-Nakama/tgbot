from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from src.tools.db import fetchrow, fetch, execute as pg_execute
from src.tools.utils.utils_hash import digest


async def get_doc_revision() -> str:
    row = await fetchrow("SELECT value FROM kv WHERE key = 'doc_revision';")
    return row["value"] if row else ""


async def set_doc_revision(new_rev: str) -> None:
    await pg_execute("UPDATE kv SET value = $1 WHERE key = 'doc_revision';", new_rev)


async def list_all_content_ids() -> list[int]:
    rows = await fetch("SELECT id FROM content;")
    return [r["id"] for r in rows]


async def delete_content_ids(ids: list[int]) -> None:
    await pg_execute("DELETE FROM content WHERE id = ANY($1::bigint[]);", ids)


async def upsert_node(
    *,
    parent_id: Optional[int],
    ord_: int,
    title: str,
    body: Optional[str],
    force_reembed_all: bool,
) -> Tuple[int, bool, bool, bool]:
    """
    Insert or update one content row by the natural key (parent_id, ord).
    Returns: (id, need_embedding, is_new, updated_changed)
    """
    txt = (body or title or "")
    dg = digest(txt)

    row = await fetchrow(
        """
        SELECT id, text_digest, parent_id, ord
          FROM content
         WHERE parent_id IS NOT DISTINCT FROM $1
           AND ord = $2;
        """,
        parent_id,
        ord_,
    )

    need_embedding = force_reembed_all
    is_new = False
    updated_changed = False

    if row is None:
        inserted = await fetchrow(
            """
            INSERT INTO content (parent_id, title, body, ord, text_digest, embedded_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id;
            """,
            parent_id,
            title,
            body,
            ord_,
            dg,
            datetime.now(tz=timezone.utc),
        )
        cid = inserted["id"]
        need_embedding = True
        is_new = True

    else:
        cid = row["id"]
        if row["text_digest"] != dg:
            await pg_execute(
                """
                UPDATE content
                   SET title       = $2,
                       body        = $3,
                       text_digest = $4,
                       embedded_at = $5
                 WHERE id = $1;
                """,
                cid,
                title,
                body,
                dg,
                datetime.now(tz=timezone.utc),
            )
            need_embedding = True
            updated_changed = True

        # Keep no-op "move" check identical to previous code path (safe)
        if row["parent_id"] != parent_id or row["ord"] != ord_:
            await pg_execute("UPDATE content SET parent_id = $2, ord = $3 WHERE id = $1;", cid, parent_id, ord_)

    return cid, need_embedding, is_new, updated_changed
