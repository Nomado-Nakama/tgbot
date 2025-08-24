from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass(slots=True)
class ContentNode:
    level: str
    title: str
    body: Optional[str] = None
    children: List["ContentNode"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass(slots=True)
class SyncStats:
    inserted: int = 0
    updated: int = 0
    moved: int = 0
    deleted: int = 0
    embedded: int = 0
