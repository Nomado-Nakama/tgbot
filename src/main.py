import asyncio
import traceback

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.types.error_event import ErrorEvent
from aiogram.exceptions import TelegramBadRequest
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from googleapiclient.errors import HttpError

from src.tools.logger import logger
from src.tools.db import fetchrow, init_pool
from src.config import settings, project_root_path
from src.content.sync.pipeline.sync import run_once
from src.bot.user_router import router as user_router
from src.tools.qdrant_high_level_client import ensure_collection
from src.activity_log import UserActionsLogMiddleware, OutgoingLoggingMiddleware

import logging
logging.basicConfig(level=logging.DEBUG)

dp = Dispatcher()
dp.include_router(user_router)


@dp.errors()
async def on_error(event: ErrorEvent) -> bool:
    """
    Global error handler.
    In aiogram-3 an error handler receives a single ErrorEvent object.
    Returning True marks the exception as handled so it will not be
    re-raised by aiogram.
    """
    exc = event.exception
    if isinstance(exc, TelegramBadRequest):
        logger.error(
            "TelegramBadRequest: %s\nOffending update (truncated):\n%s",
            exc,
            str(event.update)[:500],
        )
        return True   # exception handled – do not propagate further
    # Let everything else bubble through the default chain
    return False


@dp.message(Command("ping"))
async def ping(message: Message):
    await message.answer("pong 🏓")
    # minimal db sanity check
    row = await fetchrow("SELECT 1 AS ok;")
    logger.info(f"DB check returned: {row['ok']}")


async def main():
    bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp.update.outer_middleware(UserActionsLogMiddleware())
    bot.session.middleware(OutgoingLoggingMiddleware())

    try:
        if settings.ENABLE_VECTOR_SEARCH:
            await ensure_collection()
        try:
            await run_once(force_reembed_all_if_empty=settings.ENABLE_VECTOR_SEARCH)
        except HttpError as e:
            logger.info(f"Google docs API returned an error: {e}")

        if settings.RUNNING_ENV == "LOCAL":
            logger.info("Running in LOCAL mode with long polling.")
            await init_pool()
            await bot.delete_webhook(drop_pending_updates=True)
            logger.success("Bot started")
            await dp.start_polling(bot)
        else:
            logger.info("Running in PROD mode with webhooks.")
            app = web.Application()
            webhook_request_handler = SimpleRequestHandler(
                dispatcher=dp, bot=bot, secret_token=settings.WEBHOOK_SECRET
            )
            webhook_request_handler.register(app, path=settings.WEBHOOK_PATH)
            setup_application(app, dp, bot=bot)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host=settings.WEBAPP_HOST, port=int(settings.WEBAPP_PORT))
            await site.start()
            logger.success(f"Server started at http://{settings.WEBAPP_HOST}:{settings.WEBAPP_PORT}")

            # Run forever
            await asyncio.Event().wait()
    except Exception as exc:
        # Log the exception with full traceback
        logger.exception(f"Fatal: {exc}")
        tb = traceback.format_exc()
        tmp = project_root_path / "alert.txt"

        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(tb)

        error_message = (
            f"🚨 <b>Bot crashed with an exception</b>:\n\n"
            f"<pre>{tb}</pre>"
        )

        # Send the error message to the admin
        try:
            await bot.send_document(231584958, FSInputFile(tmp), caption=str(exc))
            await bot.send_message(
                chat_id=231584958,
                text=error_message,
                parse_mode="HTML"
            )
        except Exception as notify_error:
            logger.error(f"Failed to notify admin: {notify_error}")
        raise  # Re-raise the exception to allow further handling if necessary


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        # Log the exception with full traceback
        logger.exception(f"Fatal: {exc}")
        tb = traceback.format_exc()
        tmp = project_root_path / "alert.txt"

        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(tb)

        error_message = (
            f"🚨 <b>Bot crashed with an exception</b>:\n\n"
            f"<pre>{tb}</pre>"
        )
        logger.info(error_message)
