from __future__ import annotations

import contextvars
from typing import Any, Dict, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Context shared between dispatcher middleware (incoming) and client-session
# middleware (outgoing). We bind every outgoing "delivery" to the triggering
# activity row.
# ──────────────────────────────────────────────────────────────────────────────
CURRENT_ACTIVITY_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("activity_id", default=None)
CURRENT_USER_ID: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("user_id", default=None)
CURRENT_CHAT_ID: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("chat_id", default=None)

# Content snapshot derived at *incoming* stage (for open_{id} / save_{id}_...)
CURRENT_CONTENT_SNAPSHOT: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "content_snapshot", default=None
)

_MAX_TXT_LEN = 20_000  # hard cap just in case


def trim(txt: Optional[str]) -> Optional[str]:
    if txt is None:
        return None
    return txt if len(txt) <= _MAX_TXT_LEN else (txt[:_MAX_TXT_LEN - 1] + "…")
