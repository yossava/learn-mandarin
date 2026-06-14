"""Transcribe Mandarin audio with faster-whisper, keeping word-level timestamps."""

import json
from pathlib import Path

from faster_whisper import WhisperModel

from .config import WHISPER_COMPUTE, WHISPER_DEVICE, WHISPER_MODEL

_model = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE
        )
    return _model


def transcribe(audio_path: Path, on_progress=None) -> list[dict]:
    """Return a list of segments with word timestamps, caching to transcript.json.

    on_progress, if given, is called as (fraction, segment_count, word_count, latest_text)
    as transcription proceeds; fraction is None when the audio duration is unknown.
    """
    out = audio_path.parent / "transcript.json"
    if out.exists():
        return json.loads(out.read_text())

    segments, info = _get_model().transcribe(
        str(audio_path),
        language="zh",
        word_timestamps=True,
        vad_filter=True,
    )
    duration = info.duration or 0

    result = []
    word_count = 0
    for seg in segments:
        words = [
            {"word": w.word, "start": w.start, "end": w.end}
            for w in (seg.words or [])
        ]
        word_count += len(words)
        result.append(
            {"start": seg.start, "end": seg.end, "text": seg.text, "words": words}
        )
        if on_progress:
            frac = min(1.0, seg.end / duration) if duration else None
            on_progress(frac, len(result), word_count, seg.text.strip())

    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result
