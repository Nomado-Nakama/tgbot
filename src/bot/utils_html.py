# utils_html.py
from __future__ import annotations
from html.parser import HTMLParser
from html import escape
from typing import List

TG_TAGS = {"b", "i", "u", "s", "code", "pre", "a", "br"}


class TagChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: List[str] = []
        self.valid = True

    def handle_starttag(self, tag, attrs):
        if tag in TG_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in TG_TAGS:
            if not self.stack or self.stack[-1] != tag:
                self.valid = False  # overlap
            else:
                self.stack.pop()


def is_balanced(html: str) -> bool:
    p = TagChecker()
    p.feed(html)
    return p.valid and not p.stack


def safe_html(raw: str) -> str:
    """Return Telegram-safe HTML (no overlap, only allowed tags)."""
    try:
        import bleach  # optional but handy
        cleaned = bleach.clean(
            raw,
            tags=list(TG_TAGS),
            attributes={"a": ["href"]},
            strip=True,
        )
    except ModuleNotFoundError:
        cleaned = raw

    if is_balanced(cleaned):
        return cleaned

    # Fallback: escape everything → plain text
    return escape(cleaned)


def split_html_safe(text: str, max_len: int = 4000) -> List[str]:
    """Split only between tags, never inside <b>…>."""
    parts, buff, depth = [], [], 0
    for c in text:
        if c == "<":
            depth += 1
        buff.append(c)
        if c == ">":
            depth = max(0, depth - 1)
        if len(buff) >= max_len and depth == 0:
            parts.append("".join(buff))
            buff.clear()
    if buff:
        parts.append("".join(buff))
    return parts
