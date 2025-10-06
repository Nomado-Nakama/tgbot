from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any, Awaitable, Callable, Dict, Optional

from loguru import logger
from aiogram import BaseMiddleware
from aiogram.types import (
    TelegramObject, Update, Message, CallbackQuery, InlineQuery, ChosenInlineResult,
    ChatMemberUpdated, ShippingQuery, PreCheckoutQuery, PollAnswer
)

from src.bot.content_dao import get_content, get_breadcrumb
from src.tools.utils.utils_hash import digest
from .context import CURRENT_ACTIVITY_ID, CURRENT_USER_ID, CURRENT_CHAT_ID, CURRENT_CONTENT_SNAPSHOT, trim
from . import repository


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
    return data


def spawn_bg(coro: Awaitable[Any], label: str) -> None:
    """
    Run a coroutine in the background and log any exception.
    """
    task = asyncio.create_task(coro)
    def _done(t: asyncio.Task):
        exc = t.exception()
        if exc:
            logger.warning(f"[UALM] Background task '{label}' failed: {exc}")
    task.add_done_callback(_done)


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
            # Ensure user/chat rows exist — but do it off the critical path
            # (fire-and-forget to cut hot-path latency; idempotent upserts).
            spawn_bg(repository.upsert_user(user), "upsert_user")
            spawn_bg(repository.upsert_chat(chat), "upsert_chat")

            # Guess command (naïve, just from text)
            command = None
            if isinstance(event, Message) and event.text and event.text.startswith("/"):
                command = event.text.split()[0]

            # Determine action name (best-effort)
            action = None
            if (h := data.get("handler")) is not None:
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
                if event.data.startswith("open_") or event.data.startswith("save_"):
                    try:
                        cid = int(event.data.removeprefix("open_").removeprefix("save_").split("_", 1)[0])
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

            activity_id = await repository.insert_activity_row(
                user_id=user.id if user else None,
                chat_id=chat.id if chat else None,
                message_id=msg_id,
                update_id=update_id,
                update_type=update_type,
                action=action,
                command=command,
                state=state,
                text=trim(text),
                data_=trim(cb_data),
                payload=payload,
                meta=meta,
            )

            # Bind context for outgoing logger
            token_a = CURRENT_ACTIVITY_ID.set(activity_id)
            token_u = CURRENT_USER_ID.set(user.id if user else None)
            token_c = CURRENT_CHAT_ID.set(chat.id if chat else None)
            token_s = CURRENT_CONTENT_SNAPSHOT.set(snapshot)

            logger.info(
                f"[UALM] Inserted activity {activity_id} for user={getattr(user, 'id', None)} "
                f"chat={getattr(chat, 'id', None)} type={update_type}"
            )

            try:
                result = await handler(event, data)
                return result
            except Exception as e:
                import traceback as _tb
                tb_txt = _tb.format_exc()
                latency_ms = int(1000 * (perf_counter() - t0))
                await repository.mark_activity_error(
                    activity_id,
                    error_class=e.__class__.__name__,
                    error_message=str(e),
                    error_traceback=tb_txt,
                    latency_ms=latency_ms,
                )
                logger.exception(f"[UALM] Error during handling update {update_id} → activity={activity_id}")
                raise
            finally:
                # append latency for non-error path too
                try:
                    latency_ms = int(1000 * (perf_counter() - t0))
                    await repository.append_activity_latency(activity_id, latency_ms=latency_ms)
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
