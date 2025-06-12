from __future__ import annotations

from loguru import logger

import re
from html import escape
from typing import List
from html.parser import HTMLParser

TG_TAGS = {"b", "i", "u", "s", "code", "pre", "a", "br"}
_HASHTAG_RE = re.compile(r'(?:^|\s)#[^\s]+', flags=re.UNICODE)

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

    logger.warning("safe_html: unbalanced HTML after bleach - falling back")
    stripped = re.sub(r"<[^>]+>", "", cleaned)
    # Fallback: escape everything → plain text
    return escape(stripped)


def remove_seo_hashtags(txt_with_hashtags: str) -> str:
    """
    Strip every #hashtag token from text—even if the token is polluted with
    inline HTML tags like ``#<b>visa</b>``.

    Examples
    --------
    >>> remove_seo_hashtags("Hi #hello #world")
    'Hi'
    >>> remove_seo_hashtags("#привет мир")
    'мир'
    >>> remove_seo_hashtags("Emoji test #добро😊 #happy")
    'Emoji test'
    >>> remove_seo_hashtags("#<b>test</b> hello")
    'hello'
    """
    if "#" not in txt_with_hashtags:
        return txt_with_hashtags

    original = txt_with_hashtags
    # 1️⃣  Drop each hashtag (and any inline HTML it contains)
    cleaned = _HASHTAG_RE.sub(" ", txt_with_hashtags)
    # 2️⃣  Collapse double-spaces produced by the removal
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    # Optional debug audit
    if original != cleaned:
        logger.debug("SEO hashtags removed: %r → %r", original, cleaned)

    return cleaned


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


if __name__ == "__main__":
    print(remove_seo_hashtags("""
Для граждан РФ виза не требуется, если вы едете в Корею как турист — до 60 дней. Но обязательно нужно оформить K-ETA — это электронное разрешение на въезд:
🔹 Оформляется онлайн за 72 часа до вылета
🔹 Стоимость: ~10 000 ₩ (~700₽)
🔹 Действует: 2 года
⚠️ Без K-ETA вас не посадят на рейс



#виза"""))
