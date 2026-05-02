"""
/start — welcome message.
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

START_TEXT = """
👋 *Welcome to VideoDownloaderBot!*

Send me any public video URL and I'll download and send it back to you.

Supported sites: YouTube, Twitter/X, Instagram, TikTok, Reddit, and 1000+ more via yt-dlp.

Use /help to see all commands.
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        START_TEXT,
        parse_mode="Markdown",
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start_handler))
