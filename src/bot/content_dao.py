from dataclasses import dataclass

from src.bot.db import fetch, fetchrow


@dataclass(slots=True)
class Content:
    id: int
    parent_id: int | None
    title: str
    body: str | None
    ord: int


_SEL = "id, parent_id, title, body, ord"


async def get_children(parent: int | None) -> list[Content]:
    rows = await fetch(
        f"SELECT {_SEL} FROM content "
        "WHERE parent_id IS NOT DISTINCT FROM $1 "
        "ORDER BY ord, id;",
        parent,
    )
    return [Content(**r) for r in rows]


async def get_content(item_id: int) -> Content | None:
    row = await fetchrow(f"SELECT {_SEL} FROM content WHERE id = $1;", item_id)
    return Content(**row) if row else None
