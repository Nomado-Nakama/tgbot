from __future__ import annotations

import contextvars
import json

from time import perf_counter
from typing import Any, Awaitable, Callable, Dict, Optional

from loguru import logger

from aiogram import BaseMiddleware, Bot
from aiogram.types import (
    TelegramObject, Update, Message, CallbackQuery, InlineQuery, ChosenInlineResult,
    ChatMemberUpdated, ShippingQuery, PreCheckoutQuery, PollAnswer
)
from aiogram.methods import TelegramMethod
from aiogram.types import Message as TgMessage

from src.tools.db import execute as pg_execute, fetchrow
from src.bot.content_dao import get_content, get_breadcrumb
from src.tools.utils.utils_hash import digest

from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware, NextRequestMiddlewareType, Response as SessionResponse
)

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


def _trim(txt: Optional[str]) -> Optional[str]:
    if txt is None:
        return None
    return txt if len(txt) <= _MAX_TXT_LEN else (txt[:_MAX_TXT_LEN - 1] + "…")


async def _upsert_user_and_chat(user, chat) -> None:
    # user
    if user:
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
    # chat
    if chat:
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


def _extract_basic(event: TelegramObject) -> dict[str, Any]:
    """
    Normalize common fields across different update types.
    """
    if isinstance(event, Update):
        for attr in (
                "message", "edited_message", "callback_query", "inline_query",
                "chosen_inline_result", "channel_post", "edited_channel_post",
                "shipping_query", "pre_checkout_query", "poll_answer",
                "my_chat_member", "chat_member", "chat_join_request",
        ):
            obj = getattr(event, attr, None)
            if obj is not None:
                return _extract_basic(obj)

    data: dict[str, Any] = {
        "update_type": type(event).__name__.lower(),
        "text": None,
        "data": None,
        "message_id": None,
        "user": None,
        "chat": None,
    }

    if isinstance(event, Message):
        data["text"] = event.text or event.caption
        data["message_id"] = event.message_id
        data["user"] = event.from_user
        data["chat"] = event.chat
    elif isinstance(event, CallbackQuery):
        data["text"] = event.message.text if event.message else None
        data["data"] = event.data
        data["message_id"] = event.message.message_id if event.message else None
        data["user"] = event.from_user
        data["chat"] = event.message.chat if event.message else None
    elif isinstance(event, InlineQuery):
        data["text"] = event.query
        data["user"] = event.from_user
    elif isinstance(event, ChosenInlineResult):
        data["text"] = event.query
        data["user"] = event.from_user
    elif isinstance(event, (ChatMemberUpdated,)):
        data["user"] = event.from_user
        data["chat"] = event.chat
    elif isinstance(event, (ShippingQuery, PreCheckoutQuery, PollAnswer)):
        data["user"] = event.from_user
    # other types can be added as needed
    return data


async def _insert_activity_row(
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
        payload: dict[str, Any],
        meta: dict[str, Any],
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
        _trim(text), _trim(data_), json.dumps(payload), json.dumps(meta),
    )
    return row["id"]


class UserActionsLogMiddleware(BaseMiddleware):
    """
    Logs every incoming user action into public.bot_user_activity_log.
    Also prepares context for outgoing deliveries (activity id + optional content snapshot).
    """

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        t0 = perf_counter()

        # Recover Update for update_id if present
        upd: Optional[Update] = data.get("event_update") if isinstance(data.get("event_update"), Update) else None
        update_id = getattr(upd, "update_id", None)

        base = _extract_basic(event)
        user = base["user"]
        chat = base["chat"]
        text = base["text"]
        cb_data = base["data"]
        msg_id = base["message_id"]
        update_type = base["update_type"]
        try:
            await _upsert_user_and_chat(user, chat)

            # Guess command (naïve, just from text)
            command = None
            if isinstance(event, Message) and event.text and event.text.startswith("/"):
                command = event.text.split()[0]

            # Determine action name (best-effort)
            action = None
            if (h := data.get("handler")) is not None:
                # function or class-based; keep it readable
                action = getattr(h, "__qualname__", getattr(h, "__name__", str(h)))

            # FSM state if you use FSM (not in this repo yet)
            state = None
            if "state" in data and data["state"]:
                try:
                    state = await data["state"].get_state()
                except Exception:
                    state = None

            # If user clicked "open_{id}" or "save_{id}_<prev>", snapshot content for later delivery logging
            snapshot: Optional[Dict[str, Any]] = None
            if isinstance(event, CallbackQuery) and event.data:
                if event.data.startswith("open_"):
                    try:
                        cid = int(event.data.removeprefix("open_"))
                        content = await get_content(cid)
                        if content:
                            # Breadcrumb for UX context
                            bc_items = await get_breadcrumb(cid)
                            breadcrumb = " › ".join(i.title for i in bc_items)
                            snapshot = {
                                "content_id": cid,
                                "content_title": content.title,
                                "content_body": content.body,
                                "breadcrumb": breadcrumb,
                                "text_digest": digest((content.body or content.title or "")[:100000])
                            }
                    except Exception as e:
                        logger.warning(f"Failed to build content snapshot for {event.data}: {e}")
                elif event.data.startswith("save_"):
                    try:
                        cid = int(event.data.removeprefix("save_").split("_", 1)[0])
                        content = await get_content(cid)
                        if content:
                            bc_items = await get_breadcrumb(cid)
                            breadcrumb = " › ".join(i.title for i in bc_items)
                            snapshot = {
                                "content_id": cid,
                                "content_title": content.title,
                                "content_body": content.body,
                                "breadcrumb": breadcrumb,
                                "text_digest": digest((content.body or content.title or "")[:100000])
                            }
                    except Exception as e:
                        logger.warning(f"Failed to build content snapshot for {event.data}: {e}")

            meta = {
                "middleware": "UserActionsLogMiddleware",
                "handler_name": action,
            }
            payload = {
                "raw_kind": update_type,
            }

            activity_id = await _insert_activity_row(
                user_id=user.id if user else None,
                chat_id=chat.id if chat else None,
                message_id=msg_id,
                update_id=update_id,
                update_type=update_type,
                action=action,
                command=command,
                state=state,
                text=text,
                data_=cb_data,
                payload=payload,
                meta=meta,
            )

            # Bind context for outgoing logger
            token_a = CURRENT_ACTIVITY_ID.set(activity_id)
            token_u = CURRENT_USER_ID.set(user.id if user else None)
            token_c = CURRENT_CHAT_ID.set(chat.id if chat else None)
            token_s = CURRENT_CONTENT_SNAPSHOT.set(snapshot)

            logger.info(
                f"[UALM] Inserted activity {activity_id} for user={getattr(user, 'id', None)} chat={getattr(chat, 'id', None)} type={update_type}")

            try:
                result = await handler(event, data)
                return result
            except Exception as e:
                # Update the row as error
                import traceback as _tb
                tb_txt = _tb.format_exc()
                latency_ms = int(1000 * (perf_counter() - t0))
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
                    activity_id, e.__class__.__name__, str(e), tb_txt, latency_ms
                )

                logger.exception(f"[UALM] Error during handling update {update_id} → activity={activity_id}")
                raise
            finally:
                # append latency for non-error path too
                try:
                    latency_ms = int(1000 * (perf_counter() - t0))
                    await pg_execute(
                        """
                        UPDATE public.bot_user_activity_log
                           SET meta = meta || jsonb_build_object('latency_ms', $2::integer)
                         WHERE id = $1::uuid;
                        """,
                        activity_id, latency_ms
                    )
                except Exception as e:
                    logger.warning(f"[UALM] Failed to update latency for activity={activity_id}: {e}")

                # cleanup context
                CURRENT_ACTIVITY_ID.reset(token_a)
                CURRENT_USER_ID.reset(token_u)
                CURRENT_CHAT_ID.reset(token_c)
                CURRENT_CONTENT_SNAPSHOT.reset(token_s)
        except Exception as e:
            logger.warning(f"[UALM] Skip logging for this update: {e!r}")
            return await handler(event, data)


class OutgoingLoggingMiddleware(BaseRequestMiddleware):
    """
    Logs *outgoing* Bot API calls that produce messages (sendMessage/editMessageText/etc.)
    and binds them to CURRENT_ACTIVITY_ID (if present).
    """

    async def __call__(
            self,
            make_request: NextRequestMiddlewareType[Any],
            bot: "Bot",
            method: TelegramMethod[Any],
    ) -> Any:  # return the same thing as make_request
        method_name = type(method).__name__

        # Do the request first
        response = await make_request(bot, method)

        try:
            # If there is no activity context – skip completely (startup pings, long-polling, etc.)
            activity_id = CURRENT_ACTIVITY_ID.get()
            if activity_id is None:
                return response

            # Unwrap Response[TelegramType] if needed; otherwise use the raw result
            result_obj = response.result if isinstance(response, SessionResponse) else response

            # We only log real message deliveries
            if isinstance(result_obj, TgMessage):
                user_id = CURRENT_USER_ID.get()
                chat_id = CURRENT_CHAT_ID.get()

                sent_text = getattr(result_obj, "text", None) or getattr(result_obj, "caption", None)
                sent_text = _trim(sent_text)

                # fallback: try to read text from the method (e.g. EditMessageText)
                if sent_text is None:
                    sent_text = _trim(getattr(method, "text", None))

                snapshot = CURRENT_CONTENT_SNAPSHOT.get() or {}
                text_dg = digest(sent_text or "") if sent_text else snapshot.get("text_digest")

                await pg_execute(
                    """
                    INSERT INTO public.bot_user_deliveries
                        (activity_id, user_id, chat_id, message_id, method,
                         sent_text, text_digest, content_title, content_body, breadcrumb, payload)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb);
                    """,
                    activity_id,
                    user_id,
                    result_obj.chat.id if result_obj.chat else chat_id,
                    result_obj.message_id,
                    method_name,
                    sent_text,
                    text_dg,
                    snapshot.get("content_title"),
                    _trim(snapshot.get("content_body")),
                    snapshot.get("breadcrumb"),
                    json.dumps({"method_dump": str(method)}),
                )
                logger.info(
                    f"[OLM] Logged delivery: activity={activity_id} "
                    f"method={method_name} chat={chat_id} msg={result_obj.message_id}"
                )

        except Exception as e:
            # Keep running even if logging fails
            logger.warning(f"[OLM] Failed to log outgoing message for method={method_name}: {e}")

        return response
