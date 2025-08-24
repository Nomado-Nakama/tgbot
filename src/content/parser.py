from __future__ import annotations

from typing import List

from src.content.models import ContentNode


def parse_lines_to_nodes(raw: str) -> List[ContentNode]:
    """
    Transform the H1/H2/H3/H4-marked text into a tree of ContentNode.
    Mirrors previous logic (kept 1:1).
    """
    lines = raw.splitlines()
    nodes: list[ContentNode] = []
    node_stack: list[tuple[int, ContentNode]] = []  # (level, node)
    current_leaf: ContentNode | None = None

    def detect_level(text: str) -> int:
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
                current_leaf.body = "" if current_leaf.body is None else f"{current_leaf.body}\n"
            continue

        stripped_left = line.lstrip()

        if any(stripped_left.startswith(p) for p in ["H1:", "H2:", "H3:", "H4:"]):
            level = detect_level(stripped_left)
            clean_line = stripped_left.split(":", 1)[1].lstrip()
            node = ContentNode(level=str(level), title=clean_line, body=None, children=[])

            while node_stack and node_stack[-1][0] >= level:
                node_stack.pop()

            if node_stack:
                node_stack[-1][1].children.append(node)
            else:
                nodes.append(node)

            node_stack.append((level, node))
            current_leaf = node if level >= 3 else None

        else:
            if current_leaf:
                slice_ = line.rstrip()
                current_leaf.body = slice_ if current_leaf.body is None else f"{current_leaf.body}\n{slice_}"

    return nodes
