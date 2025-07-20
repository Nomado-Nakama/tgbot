from dataclasses import dataclass
from datetime import datetime

from src.bot.db import execute, fetch, fetchrow


class ContentNode:
    def __init__(self, level: str, title: str, body: str | None = None):
        self.level = level
        self.title = title
        self.body = body
        self.children = []
        self.parent = None

    def add_child(self, child: "ContentNode"):
        child.parent = self
        self.children.append(child)


@dataclass(slots=True)
class Content:
    id: int
    parent_id: int | None
    title: str
    body: str | None
    ord: int
    text_digest: str
    embedded_at: datetime | None


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


def parse_google_doc_text_as_list_of_content_nodes(raw: str) -> list[ContentNode]:
    lines = raw.splitlines()
    nodes: list[ContentNode] = []
    node_stack: list[tuple[int, ContentNode]] = []  # (level, node)
    current_leaf: ContentNode | None = None

    def detect_level(text: str) -> int:
        # Use style markers inserted by load_google_doc via paragraph style mapping
        if "H1:" in text:
            return 1
        elif "H2:" in text:
            return 2
        elif "H3:" in text:
            return 3
        if "H4:" in text:
            return 4
        return 5  # body

    for line in lines:
        if line == "":
            if current_leaf is not None:
                current_leaf.body = (
                    "" if current_leaf.body is None else f"{current_leaf.body}\n"
                )
            continue

        stripped_left = line.lstrip()

        # H1/H2/H3/H4 markers may have no indent – use the left-stripped variant
        if any(stripped_left.startswith(p) for p in ["H1:", "H2:", "H3:", "H4:"]):
            level = detect_level(stripped_left)
            clean_line = stripped_left.split(":", 1)[1].lstrip()
            node = ContentNode(level=str(level), title=clean_line)

            # Maintain hierarchy via stack
            while node_stack and node_stack[-1][0] >= level:
                node_stack.pop()

            if node_stack:
                node_stack[-1][1].add_child(node)
            else:
                nodes.append(node)

            node_stack.append((level, node))
            current_leaf = node if level >= 3 else None

        else:
            if current_leaf:
                slice_ = line.rstrip()
                current_leaf.body = (
                    slice_
                    if current_leaf.body is None
                    else f"{current_leaf.body}\n{slice_}"
                )

    return nodes
