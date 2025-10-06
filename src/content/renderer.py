from __future__ import annotations

from html import escape as html_escape
import re
from typing import List, Tuple

from loguru import logger

from src.content.models import Content
from src.tools.utils.utils_html import (
    safe_html,
    split_html_safe,
    remove_seo_hashtags,
    is_balanced,
)

_TAG_RE = re.compile(r"<[^>]+>")  # for plain-text fallback only


def build_breadcrumb_text(items: List[Content]) -> str:
    """
    Safe, display-ready breadcrumb string: "Parent › Child › Leaf"
    Titles are HTML-escaped so they can be safely wrapped into <b>…</b>.
    """
    return " › ".join(html_escape(i.title, quote=False) for i in items)


def _first_chunk_with_fallback(first_chunk_html: str) -> str:
    """
    Ensure the first chunk is safe for Telegram:
      1) If HTML is unbalanced even after our cleaning → strip tags and escape to plain text.
      2) Always remove SEO hashtags.
    """
    if not is_balanced(first_chunk_html):
        # strip tags → escape → plain text
        stripped = _TAG_RE.sub("", first_chunk_html)
        first_chunk_html = html_escape(stripped)

    return remove_seo_hashtags(first_chunk_html).strip()


def render_leaf_message(
    item: Content,
    breadcrumb_items: List[Content],
    *,
    max_len: int = 3800,
) -> Tuple[str, List[str]]:
    """
    Build the full text for a leaf node:
      • <b>Breadcrumb</b>
      • First content chunk
    Return (complete_text_for_edit_or_answer, extra_chunks_to_send_separately).

    Behavior mirrors the previous handlers 1:1.
    """
    # Breadcrumb
    logger.info(f"breadcrumb_items: {breadcrumb_items}...")
    breadcrumb_text = build_breadcrumb_text(breadcrumb_items)
    logger.info(f"build_breadcrumb_text: {breadcrumb_text}...")

    # Body → safe HTML
    raw_body = item.body or "…"
    body_safe = safe_html(raw_body)

    # Split into chunks respecting tag boundaries and Telegram limits
    chunks = [remove_seo_hashtags(c).strip() for c in split_html_safe(body_safe, max_len=max_len)]
    if not chunks:
        chunks = ["…"]

    first_chunk = _first_chunk_with_fallback(chunks[0])
    complete_text = remove_seo_hashtags(f"<b>{breadcrumb_text}</b>\n\n{first_chunk}")

    # Remaining chunks are already cleaned above
    extra_chunks = [c for c in chunks[1:] if c]

    return complete_text, extra_chunks
