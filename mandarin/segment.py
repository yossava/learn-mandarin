"""Group Whisper words into sentences with accurate start/end times."""

from .config import CLIP_PAD, MAX_CHARS, MAX_GAP

TERMINATORS = "。！？!?；;…"


def _flatten(segments: list[dict]) -> list[dict]:
    words = []
    for seg in segments:
        if seg.get("words"):
            words.extend(w for w in seg["words"] if w.get("start") is not None)
        else:
            words.append({"word": seg["text"], "start": seg["start"], "end": seg["end"]})
    return words


def to_sentences(segments, audio_duration=None) -> list[dict]:
    """Split the transcript into sentences on punctuation, long pauses or length."""
    words = _flatten(segments)
    sentences = []
    buf = []
    prev_end = None

    def flush():
        nonlocal buf
        if not buf:
            return
        text = "".join(w["word"] for w in buf).strip()
        if text:
            sentences.append({"text": text, "start": buf[0]["start"], "end": buf[-1]["end"]})
        buf = []

    for w in words:
        if buf and prev_end is not None and (w["start"] - prev_end) > MAX_GAP:
            flush()
        buf.append(w)
        prev_end = w["end"]

        stripped = w["word"].strip()
        ends_sentence = stripped and stripped[-1] in TERMINATORS
        length = sum(len(x["word"].strip()) for x in buf)
        if ends_sentence or length >= MAX_CHARS:
            flush()
    flush()

    for s in sentences:
        s["start"] = max(0.0, s["start"] - CLIP_PAD)
        s["end"] = s["end"] + CLIP_PAD
        if audio_duration:
            s["end"] = min(audio_duration, s["end"])

    return [s for s in sentences if s["text"] and (s["end"] - s["start"]) > 0.2]
