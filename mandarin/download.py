"""Download a YouTube video (with audio) and collect its metadata."""

import subprocess
from pathlib import Path

import yt_dlp

from .config import DATA_DIR, VIDEO_HEIGHT, WITH_VIDEO

# yt-dlp needs a JS runtime (deno) plus its EJS solver scripts to pass YouTube's
# signature challenges; this opt lets it fetch those solver components.
REMOTE_COMPONENTS = ["ejs:github"]
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".m4v", ".mov"}


def _find_video(out_dir: Path):
    for p in sorted(out_dir.glob("video.*")):
        if p.suffix.lower() in VIDEO_EXTS:
            return p
    return None


def download_media(url: str):
    """Return (audio_path, video_path, metadata).

    Downloads the video (capped at VIDEO_HEIGHT) and extracts its audio track. With
    WITH_VIDEO off, only the audio is fetched and video_path is None. Existing files
    are reused.
    """
    with yt_dlp.YoutubeDL(
        {"quiet": True, "skip_download": True, "remote_components": REMOTE_COMPONENTS}
    ) as ydl:
        info = ydl.extract_info(url, download=False)

    video_id = info["id"]
    out_dir = DATA_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / "audio.mp3"
    video_path = _find_video(out_dir)

    if WITH_VIDEO and video_path is None:
        opts = {
            "format": f"bv*[height<={VIDEO_HEIGHT}]+ba/b[height<={VIDEO_HEIGHT}]/bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": str(out_dir / "video.%(ext)s"),
            "remote_components": REMOTE_COMPONENTS,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        video_path = _find_video(out_dir)

    if not audio_path.exists():
        if video_path is not None:
            # pull the audio track out of the downloaded video
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-i", str(video_path),
                 "-vn", "-c:a", "libmp3lame", "-q:a", "0", str(audio_path)],
                check=True, capture_output=True,
            )
        else:
            opts = {
                "format": "bestaudio/best",
                "outtmpl": str(out_dir / "audio.%(ext)s"),
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
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
    return audio_path, video_path, meta
