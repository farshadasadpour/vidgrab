"""
/help — usage guide.
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

HELP_TEXT = """
📖 *How to use VideoDownloaderBot*

1. Simply paste a video URL into the chat.
2. I'll fetch the best available quality up to {max_size}MB.
3. The video will be sent back as a Telegram video file.

*Commands:*
/start — Welcome message
/help  — This guide
/status — Bot uptime & stats
/repo  — Source code link

*Supported sites:*
YouTube, Twitter/X, Instagram, TikTok, Reddit, Vimeo, Dailymotion, and 1000+ more.

*Limits:*
• Max file size: {max_size} MB
• One download at a time per user
"""

from VideoDownloaderBot import MAX_FILE_SIZE_MB


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        HELP_TEXT.format(max_size=MAX_FILE_SIZE_MB),
        parse_mode="Markdown",
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("help", help_handler))
