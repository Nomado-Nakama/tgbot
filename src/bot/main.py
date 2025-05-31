import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message
from src.bot.config import settings
from src.bot.logger import logger
from src.bot.db import fetchrow, init_pool

dp = Dispatcher()


@dp.message(Command("ping"))
async def ping(message: Message):
    await message.answer("pong 🏓")
    # minimal db sanity check
    row = await fetchrow("SELECT 1 AS ok;")
    logger.info(f"DB check returned: {row['ok']}")


async def main():
    bot = Bot(settings.BOT_TOKEN, DefaultBotProperties(parse_mode="HTML"))
    await init_pool()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.success("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
