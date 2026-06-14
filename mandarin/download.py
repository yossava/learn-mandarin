"""Download a YouTube video's audio as mp3 and collect its metadata."""

from pathlib import Path

import yt_dlp

from .config import DATA_DIR

# yt-dlp needs a JS runtime (deno) plus its EJS solver scripts to pass YouTube's
# signature challenges; this opt lets it fetch those solver components.
REMOTE_COMPONENTS = ["ejs:github"]


def download_audio(url: str) -> tuple[Path, dict]:
    """Return (path to audio.mp3, metadata). Skips the download if it already exists."""
    with yt_dlp.YoutubeDL(
        {"quiet": True, "skip_download": True, "remote_components": REMOTE_COMPONENTS}
    ) as ydl:
        info = ydl.extract_info(url, download=False)

    video_id = info["id"]
    out_dir = DATA_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / "audio.mp3"

    if not audio_path.exists():
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(out_dir / "audio.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }
            ],
            "remote_components": REMOTE_COMPONENTS,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    meta = {
        "video_id": video_id,
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "duration": info.get("duration"),
        "url": info.get("webpage_url", url),
    }
    return audio_path, meta
