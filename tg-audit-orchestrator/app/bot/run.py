"""Standalone bot runner.

Usage: python -m app.bot.run
The bot token must be set in .env as TELEGRAM_BOT_TOKEN.
"""
import asyncio
import logging

from app.bot.bot import build_application, set_bot_commands
from app.bot.notifications import set_bot
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    token = settings.telegram_bot_token
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Exiting.")
        return

    application = build_application(token)
    set_bot(application.bot)

    await application.initialize()
    await set_bot_commands(application)
    await application.start()

    logger.info("Bot started. Press Ctrl-C to stop.")
    await application.updater.start_polling(drop_pending_updates=True)

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
