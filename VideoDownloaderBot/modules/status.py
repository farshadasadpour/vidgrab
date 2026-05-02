"""
/status — uptime and download counter.
"""

import time
from datetime import timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Module-level state (reset on restart)
_start_time: float = time.time()
_download_count: int = 0


def increment_download_count() -> None:
    global _download_count
    _download_count += 1


def get_uptime() -> str:
    delta = timedelta(seconds=int(time.time() - _start_time))
    return str(delta)


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"🤖 *Bot Status*\n\n"
        f"⏱ Uptime: `{get_uptime()}`\n"
        f"📥 Downloads served: `{_download_count}`\n"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


def register(app: Application) -> None:
    app.add_handler(CommandHandler("status", status_handler))
