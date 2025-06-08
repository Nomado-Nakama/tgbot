from dataclasses import dataclass

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


_SEL = "id, parent_id, title, body, ord"


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


async def insert_node(node: ContentNode, parent_id: int | None = None, order: int = 0,
                      collected: list[tuple[int, ContentNode]] | None = None, ) -> int:
    result = await fetchrow(
        """
        INSERT INTO content (parent_id, title, body, ord)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        parent_id,
        node.title,
        node.body,
        order,
    )
    current_id = result[0]

    if collected is not None:
        collected.append((current_id, node))

    for idx, child in enumerate(node.children):
        # propagate the same accumulator so every descendant is recorded
        await insert_node(
            child,
            parent_id=current_id,
            order=idx,
            collected=collected,  # ← the missing bit
        )

    return current_id


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
        line = line.strip()
        if not line:
            continue

        # H1:/H2:/H3: are inserted by load_google_doc via paragraph style mapping
        if any(line.startswith(prefix) for prefix in ["H1:", "H2:", "H3:", "H4:"]):
            level = detect_level(line)
            clean_line = line.split(":", 1)[1].strip()
            node = ContentNode(level=str(level), title=clean_line)

            # Maintain hierarchy via stack
            while node_stack and node_stack[-1][0] >= level:
                node_stack.pop()

            if node_stack:
                node_stack[-1][1].add_child(node)
            else:
                nodes.append(node)

            node_stack.append((level, node))
            current_leaf = node if level == 4 else None


        else:
            if current_leaf:
                current_leaf.body = (

                    line if current_leaf.body is None else f"{current_leaf.body}\n{line}"

                )

    return nodes
