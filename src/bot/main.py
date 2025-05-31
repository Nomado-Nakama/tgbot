import asyncio

from aiohttp import web
from aiogram.types import Message
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from src.bot.logger import logger
from src.bot.config import settings
from src.bot.db import fetchrow, init_pool
from src.bot.user_router import router as user_router

dp = Dispatcher()

dp.include_router(user_router)


@dp.message(Command("ping"))
async def ping(message: Message):
    await message.answer("pong 🏓")
    # minimal db sanity check
    row = await fetchrow("SELECT 1 AS ok;")
    logger.info(f"DB check returned: {row['ok']}")


async def main():
    bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

    if settings.RUNNING_ENV == "LOCAL":
        """
        LOCAL ENV:
          - Use long polling instead of webhooks.
          - Typically we won't run an aiohttp server or set up ngrok locally.
        """

        logger.info("Running in LOCAL mode with long polling.")
        await init_pool()
        await bot.delete_webhook(drop_pending_updates=True)
        logger.success("Bot started")
        await dp.start_polling(bot)

    else:
        """
        PRODUCTION ENV:
          - Use aiohttp server and webhooks.
        """
        logger.info("Running in PROD mode with webhooks.")
        # Create aiohttp web application
        app = web.Application()

        # Setup request handler for the webhook path
        webhook_request_handler = SimpleRequestHandler(
            dispatcher=dp, bot=bot, secret_token=settings.WEBHOOK_SECRET
        )
        webhook_request_handler.register(app, path=settings.WEBHOOK_PATH)

        # Setup application with dispatcher and bot
        setup_application(app, dp, bot=bot)

        # Setup background tasks
        # app.on_startup.append(start_background_tasks)
        # app.on_cleanup.append(cleanup_background_tasks)

        # Finally run your aiohttp web server
        web.run_app(app, host=settings.WEBAPP_HOST, port=settings.PORT)


if __name__ == "__main__":
    asyncio.run(main())
