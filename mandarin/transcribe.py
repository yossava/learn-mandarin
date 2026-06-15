"""Transcribe Mandarin audio, keeping word-level timestamps.

Two backends:
- mlx-whisper: Apple-Silicon GPU, much faster (used automatically when available).
- faster-whisper: CPU, with live per-segment progress.

Override with WHISPER_BACKEND ("mlx" or "faster-whisper").
"""

import json
import platform
from pathlib import Path

from .config import (
    WHISPER_BACKEND,
    WHISPER_COMPUTE,
    WHISPER_DEVICE,
    WHISPER_MLX_MODEL,
    WHISPER_MODEL,
)

_model = None


def _backend() -> str:
    if WHISPER_BACKEND:
        return WHISPER_BACKEND.lower()
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            import mlx_whisper  # noqa: F401
            return "mlx"
        except ImportError:
            pass
    return "faster-whisper"


def _transcribe_mlx(audio_path: Path, on_progress) -> list[dict]:
    import mlx_whisper

    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=WHISPER_MLX_MODEL,
        language="zh",
        word_timestamps=True,
    )
    out = []
    word_count = 0
    for seg in result.get("segments", []):
        words = [
            {"word": w["word"], "start": w["start"], "end": w["end"]}
            for w in seg.get("words", [])
        ]
        word_count += len(words)
        out.append({"start": seg["start"], "end": seg["end"], "text": seg["text"], "words": words})
    if on_progress and out:
        on_progress(1.0, len(out), word_count, out[-1]["text"].strip())
    return out


def _get_faster_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(
            WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE
        )
    return _model


def _transcribe_faster(audio_path: Path, on_progress) -> list[dict]:
    segments, info = _get_faster_model().transcribe(
        str(audio_path), language="zh", word_timestamps=True, vad_filter=True
    )
    duration = info.duration or 0
    out = []
    word_count = 0
    for seg in segments:
        words = [
            {"word": w.word, "start": w.start, "end": w.end} for w in (seg.words or [])
        ]
        word_count += len(words)
        out.append({"start": seg.start, "end": seg.end, "text": seg.text, "words": words})
        if on_progress:
            frac = min(1.0, seg.end / duration) if duration else None
            on_progress(frac, len(out), word_count, seg.text.strip())
    return out


def transcribe(audio_path: Path, on_progress=None) -> list[dict]:
    """Return segments with word timestamps, caching to transcript.json.

    on_progress(fraction, segment_count, word_count, latest_text) is called as
    transcription proceeds (faster-whisper) or once at the end (mlx).
    """
    out = audio_path.parent / "transcript.json"
    if out.exists():
        return json.loads(out.read_text())

    if _backend() == "mlx":
        result = _transcribe_mlx(audio_path, on_progress)
    else:
        result = _transcribe_faster(audio_path, on_progress)

    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result
