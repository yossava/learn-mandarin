"""Cut the source audio into one mp3 per sentence with ffmpeg."""

import subprocess
from pathlib import Path


def slice_clip(audio_path: Path, start: float, end: float, out_path: Path) -> None:
    cmd = [
        "ffmpeg", "-nostdin", "-y",
        "-i", str(audio_path),
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-c:a", "libmp3lame", "-q:a", "4",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def slice_all(audio_path: Path, sentences: list[dict], out_dir: Path) -> list[str]:
    """Write sentences/NNNN.mp3 and return their file names."""
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for i, s in enumerate(sentences, 1):
        name = f"{i:04d}.mp3"
        out_path = out_dir / name
        if not out_path.exists():
            slice_clip(audio_path, s["start"], s["end"], out_path)
        names.append(name)
    return names
