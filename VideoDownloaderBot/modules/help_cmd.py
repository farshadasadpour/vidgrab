"""
/help — usage guide.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from VideoDownloaderBot import MAX_FILE_SIZE_MB


HELP_TEXT = """
🤖 *VidGrab Bot — Help*

Just send any public video URL and I'll download it for you.

━━━━━━━━━━━━━━━━━━━━
📥 *How to download*
━━━━━━━━━━━━━━━━━━━━
1. Send a video URL
2. Wait for download to finish
3. Choose where to send it:
   • 📱 *Telegram* — direct video message
   • ☁️ *S3* — upload to your bucket & get a link

━━━━━━━━━━━━━━━━━━━━
☁️ *S3 Storage Setup*
━━━━━━━━━━━━━━━━━━━━
Without S3, files are sent to Telegram _(max {max_size}MB)_.
With S3, you can upload files of any size.

Use /setup to configure your S3 bucket step by step.

━━━━━━━━━━━━━━━━━━━━
📋 *Commands*
━━━━━━━━━━━━━━━━━━━━
/start — Welcome message
/help — This guide
/setup — Configure your S3 bucket
/myconfig — View or update your S3 config
/status — Bot uptime & stats
/cancel — Cancel current S3 setup

━━━━━━━━━━━━━━━━━━━━
✅ *Supported Sites*
━━━━━━━━━━━━━━━━━━━━
Twitter/X, Instagram, TikTok, Reddit,
Vimeo, Dailymotion, Facebook, and 1000+ more.

⚠️ YouTube is not supported _(server IP blocked by YouTube)_.

━━━━━━━━━━━━━━━━━━━━
⚠️ *Limits*
━━━━━━━━━━━━━━━━━━━━
• Telegram upload max: {max_size} MB
• S3 upload: unlimited
• One download at a time per user
"""


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Setup S3", callback_data="start_setup")],
        [InlineKeyboardButton("📊 Bot Status", callback_data="show_status")],
    ])

    await update.effective_message.reply_text(
        HELP_TEXT.format(max_size=MAX_FILE_SIZE_MB),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("help", help_handler))