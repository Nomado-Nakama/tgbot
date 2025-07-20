import pytest

from src.bot.content_dao import get_children
from src.tools.db import execute, fetch


@pytest.mark.asyncio
async def test_get_children_happy_path():
    """
    Inserts two root records, verifies they are returned by get_children(None),
    then deletes them no matter what.

    Runs safely against a non-empty production DB.
    """
    inserted_ids: list[int] = []

    try:
        # ── seed ──────────────────────────────────────────────────────────────
        rows = await fetch(
            """
            INSERT INTO content (title)
            VALUES ($1), ($2)
            RETURNING id;
            """,
            "Root 1",
            "Root 2",
        )
        inserted_ids = [row["id"] for row in rows]

        # ── act ───────────────────────────────────────────────────────────────
        roots = await get_children(None)
        titles = {r.title for r in roots}

        # ── assert ────────────────────────────────────────────────────────────
        assert {"Root 1", "Root 2"}.issubset(titles)

    finally:
        # ── clean-up ──────────────────────────────────────────────────────────
        if inserted_ids:
            await execute(
                "DELETE FROM content WHERE id = ANY($1::bigint[]);",
                inserted_ids,
            )
