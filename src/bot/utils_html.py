from __future__ import annotations

from loguru import logger

import re
from html import escape
from typing import List, Final
from html.parser import HTMLParser

TG_TAGS = {"b", "i", "u", "s", "code", "pre", "a", "br"}
_INLINE_TAGS = TG_TAGS - {"a", "br"}  # <a> needs href; <br> is empty

_HASHTAG_RE: Final[re.Pattern[str]] = re.compile(
    rf"""
    (?<![=&\w])                                # not inside an attribute/word
    (?:                                        # optional leading wrappers
        (?:<(?:{'|'.join(_INLINE_TAGS)})[^>]*>\s*)*   # one or more inline tags
    )?
    \#                                         # literal “#”
    (?:<[^>]*>\s*)*                            # tags right after the hash
    [^\s#<]+                                   # hashtag body itself
    (?:\s*<[^>]*>)*                            # trailing/closing tags
    """,
    flags=re.UNICODE | re.VERBOSE | re.IGNORECASE,
)

_EMPTY_INLINE_TAG_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)<({tags})[^>]*>\s*</\1>".format(tags="|".join(_INLINE_TAGS))
)


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


def remove_seo_hashtags(txt: str) -> str:
    """
    Remove every `#hashtag` token – even if split by inline tags.
    """
    if "#" not in txt:
        return txt

    original = txt

    # 1. kill hashtags
    txt = _HASHTAG_RE.sub(" ", txt)

    # 2. remove empty wrappers that are now useless
    txt = _EMPTY_INLINE_TAG_RE.sub(" ", txt)

    # 3. squeeze whitespace
    txt = " ".join(txt.split())

    if original != txt:
        logger.debug(f"SEO hashtags removed: {original} → {txt}")

    return txt


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
    cases = [
        "#hello world",
        "#<b>visa</b> required",
        "<i>#документы </i> Всё ок",
        "mix #tag1 <b>#tag2</b> text",
    ]
    for c in cases:
        print(repr(remove_seo_hashtags(c)))
