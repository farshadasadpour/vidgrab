"""
Entry point: python3 -m VideoDownloaderBot
"""

from telegram.ext import Application

from VideoDownloaderBot import BOT_TOKEN, LOGGER
from VideoDownloaderBot.modules import (
    cleanup,
    download,
    help_cmd,
    history,
    start,
    status,
    user_config,
)


def build_application() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    start.register(app)
    help_cmd.register(app)
    user_config.register(app)   # ← must be before download
    history.register(app)
    download.register(app)
    status.register(app)
    cleanup.register(app)

    return app


def main() -> None:
    LOGGER.info("Starting VideoDownloaderBot …")
    app = build_application()
    app.run_polling(drop_pending_updates=True)
    LOGGER.info("Bot stopped.")


if __name__ == "__main__":
    main()