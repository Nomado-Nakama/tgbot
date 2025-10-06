from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Hashable, Optional, List

from src.content.models import Content
from src.bot.content_dao import get_children, get_content, get_breadcrumb
from src.content import build_breadcrumb_text, render_leaf_message
from src.bot.keyboard import _clean_for_btn


# Minimal LRU + TTL cache
class TTLCache:
    def __init__(self, ttl_seconds: int = 120, maxsize: int = 1024):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._store: "OrderedDict[Hashable, tuple[float, Any]]" = OrderedDict()

    def _purge(self) -> None:
        now = time.time()
        # drop expired
        for k, (exp, _) in list(self._store.items()):
            if exp < now:
                self._store.pop(k, None)
        # enforce size
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def get(self, key: Hashable) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        exp, val = item
        if exp < time.time():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return val

    def set(self, key: Hashable, value: Any) -> None:
        self._store[key] = (time.time() + self.ttl, value)
        self._purge()


# DB-bound: короткий TTL, ограниченный размер
_cache_get_content = TTLCache(ttl_seconds=3600, maxsize=4096*4)
_cache_get_children = TTLCache(ttl_seconds=3600, maxsize=4096*4)
_cache_get_breadcrumb = TTLCache(ttl_seconds=3600, maxsize=4096*4)

# CPU/строки: TTL подольше
_cache_clean_btn = TTLCache(ttl_seconds=3600, maxsize=8192*4)
_cache_breadcrumb_text = TTLCache(ttl_seconds=3600, maxsize=4096*4)
_cache_render_leaf = TTLCache(ttl_seconds=3600, maxsize=4096*4)


# Keys
def _key_children(parent_id: Optional[int]) -> tuple[str, Optional[int]]:
    return "children", parent_id


def _key_content(item_id: int) -> tuple[str, int]:
    return "content", item_id


def _key_breadcrumb(item_id: int) -> tuple[str, int]:
    return "breadcrumb_chain", item_id


def _key_clean_btn(text: str) -> tuple[str, str]:
    return "clean_btn", text


def _key_breadcrumb_text(items: List[Content]) -> tuple[str, tuple[tuple[int, str], ...]]:
    return "breadcrumb_text", tuple((i.id, i.title) for i in items)


def _key_render_leaf(item: Content, breadcrumb_items: List[Content], max_len: int) -> tuple[
    str, int, str, int, tuple[tuple[int, str], ...]
]:
    # text_digest меняется при обновлении контента → естественная инвалидация
    return (
        "render_leaf",
        item.id,
        item.text_digest,
        max_len,
        tuple((i.id, i.title) for i in breadcrumb_items),
    )


# Cached wrappers (public API)
async def get_content_cached(item_id: int) -> Content | None:
    k = _key_content(item_id)
    v = _cache_get_content.get(k)
    if v is not None:
        return v
    v = await get_content(item_id)
    _cache_get_content.set(k, v)
    return v


async def get_children_cached(parent_id: Optional[int]) -> list[Content]:
    k = _key_children(parent_id)
    v = _cache_get_children.get(k)
    if v is not None:
        return v
    v = await get_children(parent_id)
    _cache_get_children.set(k, v)
    return v


async def get_breadcrumb_cached(item_id: int) -> list[Content]:
    k = _key_breadcrumb(item_id)
    v = _cache_get_breadcrumb.get(k)
    if v is not None:
        return v
    v = await get_breadcrumb(item_id)
    _cache_get_breadcrumb.set(k, v)
    return v


def _clean_for_btn_cached(text: str) -> str:
    k = _key_clean_btn(text)
    v = _cache_clean_btn.get(k)
    if v is not None:
        return v
    v = _clean_for_btn(text)
    _cache_clean_btn.set(k, v)
    return v


def build_breadcrumb_text_cached(items: List[Content]) -> str:
    k = _key_breadcrumb_text(items)
    v = _cache_breadcrumb_text.get(k)
    if v is not None:
        return v
    v = build_breadcrumb_text(items)
    _cache_breadcrumb_text.set(k, v)
    return v


def render_leaf_message_cached(item: Content, breadcrumb_items: List[Content], *, max_len: int = 3800):
    k = _key_render_leaf(item, breadcrumb_items, max_len)
    v = _cache_render_leaf.get(k)
    if v is not None:
        return v
    v = render_leaf_message(item, breadcrumb_items, max_len=max_len)
    _cache_render_leaf.set(k, v)
    return v
