"""Cut the source media into one clip per sentence: an mp3 plus an optional mp4."""

import subprocess
from pathlib import Path

from .config import VIDEO_HEIGHT


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def slice_audio(audio_path: Path, start: float, end: float, out_path: Path) -> None:
    _run([
        "ffmpeg", "-nostdin", "-y",
        "-i", str(audio_path),
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
        "-c:a", "libmp3lame", "-q:a", "4",
        str(out_path),
    ])


def slice_video(video_path: Path, start: float, end: float, out_path: Path) -> None:
    _run([
        "ffmpeg", "-nostdin", "-y",
        "-ss", f"{start:.3f}", "-i", str(video_path), "-t", f"{end - start:.3f}",
        "-vf", f"scale=-2:'min({VIDEO_HEIGHT},ih)'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-c:a", "aac", "-movflags", "+faststart",
        str(out_path),
    ])


def slice_all(audio_path, video_path, sentences, out_dir: Path, on_progress=None) -> list[str]:
    """Write sentences/NNNN.mp3 (and NNNN.mp4 when a video is available).

    Returns the clip basenames (e.g. "0001").
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    total = len(sentences)
    for i, s in enumerate(sentences, 1):
        base = f"{i:04d}"
        audio_out = out_dir / f"{base}.mp3"
        video_out = out_dir / f"{base}.mp4"
        if not audio_out.exists():
            slice_audio(audio_path, s["start"], s["end"], audio_out)
        if video_path is not None and not video_out.exists():
            slice_video(video_path, s["start"], s["end"], video_out)
        names.append(base)
        if on_progress and total:
            on_progress(i / total)
    return names
