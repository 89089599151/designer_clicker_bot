"""Entry point for the Designer Clicker bot."""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import LOGGER, SETTINGS, setup_logging
from bot.constants import RU
from bot.database.base import init_models
from bot.database.models import Base
from bot.handlers import setup_routers
from bot.middlewares.rate_limit import RateLimitMiddleware


async def main() -> None:
    """Run bot polling loop."""

    if not SETTINGS.BOT_TOKEN or ":" not in SETTINGS.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден или неверен. Укажите его в .env (BOT_TOKEN=...)")

    setup_logging()
    await init_models(Base.metadata)

    bot = Bot(SETTINGS.BOT_TOKEN)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(setup_routers())
    dispatcher.message.middleware(RateLimitMiddleware())

    await bot.delete_webhook(drop_pending_updates=True)
    LOGGER.info("%s", RU.BOT_STARTED)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Bot stopped.")
