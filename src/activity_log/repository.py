from __future__ import annotations

import json
from typing import Any, Optional

from src.tools.db import execute as pg_execute, fetchrow


async def upsert_user(user: Any) -> None:
    if not user:
        return
    await pg_execute(
        """
        INSERT INTO public.tg_users (user_id, is_bot, first_name, last_name, username, language_code, is_premium)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (user_id) DO UPDATE SET
            is_bot = EXCLUDED.is_bot,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            username = EXCLUDED.username,
            language_code = EXCLUDED.language_code,
            is_premium = EXCLUDED.is_premium,
            updated_at = now();
        """,
        user.id, bool(getattr(user, "is_bot", False)),
        getattr(user, "first_name", None),
        getattr(user, "last_name", None),
        getattr(user, "username", None),
        getattr(user, "language_code", None),
        getattr(user, "is_premium", None),
    )


async def upsert_chat(chat: Any) -> None:
    if not chat:
        return
    await pg_execute(
        """
        INSERT INTO public.tg_chats (chat_id, type, title, username, first_name, last_name)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (chat_id) DO UPDATE SET
            type = EXCLUDED.type,
            title = EXCLUDED.title,
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            updated_at = now();
        """,
        chat.id, getattr(chat, "type", None), getattr(chat, "title", None),
        getattr(chat, "username", None), getattr(chat, "first_name", None), getattr(chat, "last_name", None),
    )


async def insert_activity_row(
    *,
    user_id: int | None,
    chat_id: int | None,
    message_id: int | None,
    update_id: int | None,
    update_type: str,
    action: str | None,
    command: str | None,
    state: str | None,
    text: str | None,
    data_: str | None,
    payload: dict,
    meta: dict,
) -> str:
    row = await fetchrow(
        """
        INSERT INTO public.bot_user_activity_log
            (user_id, chat_id, message_id, update_id, update_type, action, command, state,
             text, data, payload, meta)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12::jsonb)
        RETURNING id::text;
        """,
        user_id, chat_id, message_id, update_id, update_type, action, command, state,
        text, data_, json.dumps(payload), json.dumps(meta),
    )
    return row["id"]


async def mark_activity_error(activity_id: str, *, error_class: str, error_message: str, error_traceback: str, latency_ms: int) -> None:
    await pg_execute(
        """
        UPDATE public.bot_user_activity_log
           SET is_error = TRUE,
               error_class = $2,
               error_message = $3,
               error_traceback = $4,
               meta = meta || jsonb_build_object('latency_ms', $5::integer)
         WHERE id = $1::uuid;
        """,
        activity_id, error_class, error_message, error_traceback, latency_ms
    )


async def append_activity_latency(activity_id: str, *, latency_ms: int) -> None:
    await pg_execute(
        """
        UPDATE public.bot_user_activity_log
           SET meta = meta || jsonb_build_object('latency_ms', $2::integer)
         WHERE id = $1::uuid;
        """,
        activity_id, latency_ms
    )


async def insert_delivery(
    *,
    activity_id: str,
    user_id: Optional[int],
    chat_id: Optional[int],
    message_id: int,
    method_name: str,
    sent_text: Optional[str],
    text_digest: Optional[str],
    content_title: Optional[str],
    content_body: Optional[str],
    breadcrumb: Optional[str],
    method_dump: str,
) -> None:
    await pg_execute(
        """
        INSERT INTO public.bot_user_deliveries
            (activity_id, user_id, chat_id, message_id, method,
             sent_text, text_digest, content_title, content_body, breadcrumb, payload)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb);
        """,
        activity_id, user_id, chat_id, message_id, method_name,
        sent_text, text_digest, content_title, content_body, breadcrumb,
        json.dumps({"method_dump": method_dump}),
    )
