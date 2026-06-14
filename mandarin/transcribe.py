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

    on_progress, if given, is called with a 0..1 fraction as transcription proceeds.
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
    for seg in segments:
        words = [
            {"word": w.word, "start": w.start, "end": w.end}
            for w in (seg.words or [])
        ]
        result.append(
            {"start": seg.start, "end": seg.end, "text": seg.text, "words": words}
        )
        if on_progress and duration:
            on_progress(min(1.0, seg.end / duration))

    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result
