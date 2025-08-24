from src.content import Content
from src.tools.db import execute, fetch, fetchrow


_SEL = "id, parent_id, title, body, ord, text_digest, embedded_at"


async def get_breadcrumb(item_id: int) -> list[Content]:
    """
    Возвращает список объектов Content,
    начиная с корня и заканчивая `item_id`.
    """
    chain: list[Content] = []

    current_id: int | None = item_id
    while current_id is not None:
        item = await get_content(current_id)
        if item is None:
            break
        chain.append(item)
        current_id = item.parent_id

    return list(reversed(chain))


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


async def remove_all_content() -> int:
    return await execute("DELETE FROM content;")
