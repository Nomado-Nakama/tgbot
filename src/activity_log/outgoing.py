from __future__ import annotations

from typing import Any

from loguru import logger
from aiogram.methods import TelegramMethod
from aiogram.types import Message as TgMessage
from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware, NextRequestMiddlewareType, Response as SessionResponse
)

from src.tools.utils.utils_hash import digest
from .context import CURRENT_ACTIVITY_ID, CURRENT_USER_ID, CURRENT_CHAT_ID, CURRENT_CONTENT_SNAPSHOT, trim
from . import repository


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
                sent_text = trim(sent_text)

                # fallback: try to read text from the method (e.g. EditMessageText)
                if sent_text is None:
                    sent_text = trim(getattr(method, "text", None))

                snapshot = CURRENT_CONTENT_SNAPSHOT.get() or {}
                text_dg = digest(sent_text or "") if sent_text else snapshot.get("text_digest")

                await repository.insert_delivery(
                    activity_id=activity_id,
                    user_id=user_id,
                    chat_id=(result_obj.chat.id if result_obj.chat else chat_id),
                    message_id=result_obj.message_id,
                    method_name=method_name,
                    sent_text=sent_text,
                    text_digest=text_dg,
                    content_title=snapshot.get("content_title"),
                    content_body=trim(snapshot.get("content_body")),
                    breadcrumb=snapshot.get("breadcrumb"),
                    method_dump=str(method),
                )
                logger.info(
                    f"[OLM] Logged delivery: activity={activity_id} "
                    f"method={method_name} chat={chat_id} msg={result_obj.message_id}"
                )

        except Exception as e:
            # Keep running even if logging fails
            logger.warning(f"[OLM] Failed to log outgoing message for method={method_name}: {e}")

        return response
