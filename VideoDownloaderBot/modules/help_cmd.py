from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from VideoDownloaderBot import MAX_FILE_SIZE_MB

HELP_TEXT = """
🤖 *VidGrab Bot — Help*

Just send any public video URL and I'll download it for you.

━━━━━━━━━━━━━━━━━━━━
📥 *How to download*
━━━━━━━━━━━━━━━━━━━━
1. Send a video URL
2. Wait for download
3. Choose: 📱 Telegram or ☁️ S3

━━━━━━━━━━━━━━━━━━━━
☁️ *S3 Storage Setup*
━━━━━━━━━━━━━━━━━━━━
Without S3, files sent to Telegram (max {max_size}MB).
With S3, upload files of any size.

━━━━━━━━━━━━━━━━━━━━
📋 *Commands*
━━━━━━━━━━━━━━━━━━━━
/start — Welcome message
/help — This guide
/setup — Configure your S3 bucket step by step
/myconfig — View or update your S3 config
/status — Bot uptime and stats
/cancel — Cancel current S3 setup

━━━━━━━━━━━━━━━━━━━━
✅ *Supported Sites*
━━━━━━━━━━━━━━━━━━━━
Twitter/X, Instagram, TikTok, Reddit,
Vimeo, Dailymotion, Facebook, and 1000+ more.

⚠️ YouTube is not supported (server IP blocked).

━━━━━━━━━━━━━━━━━━━━
⚠️ *Limits*
━━━━━━━━━━━━━━━━━━━━
- Telegram max: {max_size} MB
- S3: unlimited
- One download at a time per user
"""

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        HELP_TEXT.format(max_size=MAX_FILE_SIZE_MB),
        parse_mode="Markdown",
    )

def register(app: Application) -> None:
    app.add_handler(CommandHandler("help", help_handler))