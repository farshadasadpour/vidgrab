"""
/start — welcome message.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Help & Commands", callback_data="show_help")],
        [InlineKeyboardButton("⚙️ Setup S3 Storage", callback_data="start_setup")],
    ])

    await update.effective_message.reply_text(
        "👋 *Welcome to VidGrab Bot!*\n\n"
        "Send me any public video URL and I'll download it for you.\n\n"
        "📱 *No S3?* Files sent directly to Telegram _(max 50MB)_\n"
        "☁️ *With S3?* Upload files of any size to your own bucket\n\n"
        "Use /setup to configure your S3 bucket.\n"
        "Use /help to see all commands.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start_handler))