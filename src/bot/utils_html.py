from __future__ import annotations

import re
from html import escape
from typing import List
from html.parser import HTMLParser

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


def remove_seo_hashtags(txt_with_hashtags: str) -> str:
    """
    Remove every #hashtag token (Unicode-aware) from an arbitrary sentence.

    Examples
    --------
    >>> remove_seo_hashtags("Hi #hello #world")
    'Hi'
    >>> remove_seo_hashtags("#привет мир")
    'мир'
    >>> remove_seo_hashtags("Emoji test #добро😊 #happy")
    'Emoji test'
    """
    if "#" not in txt_with_hashtags:
        return txt_with_hashtags

    # 1️⃣ drop each hashtag together with the space that precedes it (if any)
    #    – (^|\s)  … at start-of-string OR preceded by whitespace
    #    – #[^\s#]+ … a “#” followed by one-or-more non-space, non-hash chars
    result = re.sub(r"(?:^|\s)#[^\s#]+", " ", txt_with_hashtags, flags=re.UNICODE)

    # 2️⃣ collapse multiple spaces created by the substitution
    result = re.sub(r"\s{2,}", " ", result)

    return result.strip()


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

    # balance each chunk: close orphan tags
    balanced = []

    for chunk in parts:
        checker = TagChecker()
        checker.feed(chunk)
        if checker.stack:  # still-open tags → append closing partners
            chunk += "".join(f"</{tag}>" for tag in reversed(checker.stack))
        balanced.append(chunk)

    return balanced
