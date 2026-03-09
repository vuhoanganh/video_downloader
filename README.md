# 🎬 Video Saver Web

Self-hosted web app to download videos from **X/Twitter, Facebook, YouTube, TikTok, Instagram** and 1000+ sites.  
Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Features

- Paste URL → Get video info (title, thumbnail, formats)
- Choose quality / format before downloading
- Real-time download progress with speed indicator
- Auto-cleanup old files (2 hours)
- Mobile-friendly UI
- No ads, no tracking, no third-party servers

## Quick Start

```bash
# 1. Clone / copy the project
# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
```

Open **http://localhost:5000** in your browser.

## Requirements

- Python 3.10+
- ffmpeg (recommended, for merging video+audio streams)

### Install ffmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (winget)
winget install ffmpeg
```

## Deploy on VPS / Server

```bash
# Using gunicorn (production)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Or with Docker (create your own Dockerfile)
```

## Project Structure

```
video-saver/
├── app.py              # Flask backend + yt-dlp integration
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Frontend UI
└── downloads/          # Temporary downloaded files (auto-cleanup)
```

## Supported Platforms

Any site supported by yt-dlp, including:
X/Twitter, Facebook, YouTube, TikTok, Instagram, Reddit, Vimeo, Dailymotion, Twitch, SoundCloud, and many more.

## ⚠️ Disclaimer

This tool is for **personal use only**. Respect copyright laws and the original content creators' rights. Do not use for distributing copyrighted material.

---

Built with ❤️ — Anti Gravity Team
