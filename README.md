# VidGrab Bot

A Telegram bot that downloads public videos from 1000+ sites and lets you choose to send them via Telegram or upload to your own S3 bucket.

---

## Features

- 📥 Download from Twitter/X, Instagram, TikTok, Reddit, Vimeo, Dailymotion, Facebook, and 1000+ more
- 📱 Send directly to Telegram (up to 50MB)
- ☁️ Upload to your own S3 bucket (unlimited size)
- 📊 Live download & upload progress bar
- 👤 Per-user S3 configuration
- 🔒 Secret key deleted from chat immediately after entry
- 🧹 Auto cleanup of old files every hour
- ⚠️ YouTube not supported (server IPs are blocked by YouTube)

---

## Project Structure

```
vidgrab/
├── VideoDownloaderBot/
│   ├── __init__.py          # Config & shared state
│   ├── __main__.py          # Entry point
│   └── modules/
│       ├── __init__.py
│       ├── cleanup.py       # Auto file cleanup
│       ├── download.py      # Core download & upload logic
│       ├── help_cmd.py      # /help command
│       ├── start.py         # /start command
│       ├── status.py        # /status command
│       └── user_config.py   # Per-user S3 setup wizard
├── downloads/               # Temp download directory (auto-created)
├── user_configs/            # Per-user S3 configs (auto-created)
├── cookies.txt              # Optional cookies file
├── requirements.txt
├── sample.env
└── README.md
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/farshadasadpour/vidgrab.git
cd vidgrab
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install "python-telegram-bot[job-queue]"
```

### 4. Install ffmpeg (required for merging video+audio)

```bash
sudo apt install ffmpeg -y
```

### 5. Configure environment

```bash
cp sample.env .env
nano .env
```

Fill in your values:

```env
BOT_TOKEN=your_bot_token_here
OWNER_ID=your_telegram_user_id
MAX_FILE_SIZE_MB=50
DOWNLOAD_DIR=downloads
YOUTUBE_COOKIES=cookies.txt
CLEANUP_MAX_AGE_HOURS=1
CLEANUP_INTERVAL_HOURS=1
```

### 6. Run manually to test

```bash
source venv/bin/activate
python3 -m VideoDownloaderBot
```

---

## Run as a systemd Service

### 1. Create the service file

```bash
nano /etc/systemd/system/videobot.service
```

Paste the following:

```ini
[Unit]
Description=VideoDownloaderBot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/vidgrab
ExecStart=/root/vidgrab/venv/bin/python3 -m VideoDownloaderBot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Enable and start

```bash
systemctl daemon-reload
systemctl enable videobot
systemctl start videobot
```

### 3. Check status

```bash
systemctl status videobot
```

### 4. Useful commands

```bash
# View live logs
journalctl -u videobot -f

# Restart the bot
systemctl restart videobot

# Stop the bot
systemctl stop videobot

# Disable autostart
systemctl disable videobot
```

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Full usage guide |
| `/setup` | Configure your S3 bucket (step-by-step wizard) |
| `/myconfig` | View, update or delete your S3 config |
| `/status` | Bot uptime and download count |
| `/cancel` | Cancel current S3 setup wizard |

---

## S3 Setup (for users)

Send `/setup` to the bot and follow the step-by-step wizard:

1. Send your S3 endpoint URL
2. Send your Access Key
3. Send your Secret Key _(deleted from chat immediately)_
4. Send your Bucket Name
5. Confirm and save

Use `/myconfig` to view or update your config anytime.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | Telegram bot token from @BotFather |
| `OWNER_ID` | ✅ | — | Your Telegram user ID |
| `MAX_FILE_SIZE_MB` | ❌ | 50 | Max Telegram upload size in MB |
| `DOWNLOAD_DIR` | ❌ | downloads | Temp download directory |
| `YOUTUBE_COOKIES` | ❌ | cookies.txt | Path to YouTube cookies file |
| `CLEANUP_MAX_AGE_HOURS` | ❌ | 1 | Delete files older than N hours |
| `CLEANUP_INTERVAL_HOURS` | ❌ | 1 | Run cleanup every N hours |

---

## License

GPL-3.0