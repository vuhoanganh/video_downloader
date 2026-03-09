#!/usr/bin/env python3
"""
Video Saver Web — powered by yt-dlp
A self-hosted web app to download videos from X/Twitter, Facebook, YouTube, and more.
"""

import os
import json
import uuid
import threading
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

DOWNLOAD_DIR = Path(__file__).parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Track download progress
download_tasks = {}


def cleanup_old_files(max_age_hours=2):
    """Remove downloaded files older than max_age_hours."""
    now = time.time()
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > max_age_hours * 3600:
            f.unlink(missing_ok=True)


def get_video_info(url):
    """Extract video info without downloading."""
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []
    seen = set()

    if info.get('formats'):
        for f in info['formats']:
            ext = f.get('ext', 'mp4')
            height = f.get('height')
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            filesize = f.get('filesize') or f.get('filesize_approx')
            format_id = f.get('format_id', '')

            # Only include formats with video
            if vcodec == 'none' and acodec == 'none':
                continue

            has_video = vcodec != 'none'
            has_audio = acodec != 'none'

            if has_video and height:
                label = f"{height}p"
                if has_audio:
                    label += " (video+audio)"
                else:
                    label += " (video only)"
            elif not has_video and has_audio:
                label = "Audio only"
            else:
                label = f.get('format_note', format_id)

            key = (height, has_audio, ext)
            if key in seen:
                continue
            seen.add(key)

            formats.append({
                'format_id': format_id,
                'ext': ext,
                'height': height or 0,
                'label': label,
                'filesize': filesize,
                'has_video': has_video,
                'has_audio': has_audio,
            })

    # Sort: highest quality first
    formats.sort(key=lambda x: (x['has_video'], x['has_audio'], x['height']), reverse=True)

    # Limit to top useful formats
    if len(formats) > 8:
        formats = formats[:8]

    return {
        'title': info.get('title', 'Unknown'),
        'thumbnail': info.get('thumbnail', ''),
        'duration': info.get('duration', 0),
        'uploader': info.get('uploader', 'Unknown'),
        'platform': info.get('extractor', 'Unknown'),
        'url': url,
        'formats': formats,
    }


def download_video(task_id, url, format_id=None):
    """Download video in background thread."""
    import yt_dlp

    output_template = str(DOWNLOAD_DIR / f"{task_id}.%(ext)s")

    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'merge_output_format': 'mp4',
    }

    if format_id and format_id != 'best':
        # Try to get video+audio merged
        ydl_opts['format'] = f"{format_id}+bestaudio[ext=m4a]/best"
    else:
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)

            if total > 0:
                percent = round(downloaded / total * 100, 1)
            else:
                percent = 0

            download_tasks[task_id].update({
                'status': 'downloading',
                'percent': percent,
                'speed': speed,
                'eta': eta,
            })
        elif d['status'] == 'finished':
            download_tasks[task_id]['status'] = 'processing'
            download_tasks[task_id]['percent'] = 100

    ydl_opts['progress_hooks'] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the downloaded file
        for f in DOWNLOAD_DIR.iterdir():
            if f.stem == task_id and f.is_file():
                download_tasks[task_id].update({
                    'status': 'complete',
                    'filename': f.name,
                    'filesize': f.stat().st_size,
                })
                return

        download_tasks[task_id]['status'] = 'error'
        download_tasks[task_id]['error'] = 'File not found after download'

    except Exception as e:
        download_tasks[task_id]['status'] = 'error'
        download_tasks[task_id]['error'] = str(e)


# ─── Routes ───────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/info', methods=['POST'])
def api_info():
    """Get video info from URL."""
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/download', methods=['POST'])
def api_download():
    """Start a download task."""
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    # Cleanup old files
    cleanup_old_files()

    task_id = str(uuid.uuid4())[:12]
    download_tasks[task_id] = {
        'status': 'starting',
        'percent': 0,
        'speed': 0,
        'eta': 0,
        'error': None,
        'filename': None,
    }

    thread = threading.Thread(target=download_video, args=(task_id, url, format_id))
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id})


@app.route('/api/progress/<task_id>')
def api_progress(task_id):
    """Check download progress."""
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)


@app.route('/api/file/<task_id>')
def api_file(task_id):
    """Download the completed file."""
    task = download_tasks.get(task_id)
    if not task or task['status'] != 'complete':
        return jsonify({'error': 'File not ready'}), 404

    filepath = DOWNLOAD_DIR / task['filename']
    if not filepath.exists():
        return jsonify({'error': 'File not found'}), 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=task['filename'],
    )


if __name__ == '__main__':
    print("\n🎬 Video Saver Web — powered by yt-dlp")
    print("   Open http://localhost:5001 in your browser\n")
    app.run(host='0.0.0.0', port=5001, debug=False)
