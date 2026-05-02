# VideoDownloaderBot

A Telegram bot that downloads public videos from 1000+ sites (YouTube, Twitter/X, TikTok, Instagram, Reddit, Vimeo, etc.) and sends them back as Telegram video files.

Built in the same structural pattern as [Phubdlbot](https://github.com/tzmat/Phubdlbot).

---

## Project Structure

```
VideoDownloaderBot/
├── VideoDownloaderBot/
│   ├── __init__.py          # Config & shared state (loaded from .env)
│   ├── __main__.py          # Entry point — registers handlers & starts polling
│   └── modules/
│       ├── __init__.py
│       ├── start.py         # /start command
│       ├── help_cmd.py      # /help command
│       ├── status.py        # /status command
│       └── download.py      # Core: URL detection → yt-dlp → send video
├── downloads/               # Temp download directory (auto-created)
├── requirements.txt
├── sample.env
└── README.md
```

---

## Setup (VPS)

```bash
sudo apt update && apt upgrade -y
sudo apt install git python3-pip ffmpeg -y

git clone <your-repo>
cd VideoDownloaderBot

pip3 install -U -r requirements.txt

cp sample.env .env
nano .env   # fill in BOT_TOKEN and OWNER_ID

python3 -m VideoDownloaderBot
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Your Telegram bot token from @BotFather |
| `OWNER_ID` | ✅ | Your Telegram user ID |
| `LOG_CHANNEL` | ❌ | Channel ID for logs (optional) |
| `MAX_FILE_SIZE_MB` | ❌ | Max video size in MB (default: 50) |
| `DOWNLOAD_DIR` | ❌ | Download directory (default: `downloads`) |

---

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Usage guide |
| `/status` | Uptime and download count |

---

## How it Works

1. User sends a message with a URL.
2. `download.py` extracts the URL with a regex.
3. `yt-dlp` downloads the best quality video ≤ `MAX_FILE_SIZE_MB`.
4. Bot sends the video back and deletes the local file.

---

## License

GPL-3.0
