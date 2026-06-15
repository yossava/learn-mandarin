"""Group Whisper words into Mandarin-only sentences with tight clip timings.

English/Latin words are dropped before cutting, so each clip spans the spoken Chinese
and the card text contains no English.
"""

import re

from .config import CLIP_PAD, MAX_CHARS, MAX_GAP

TERMINATORS = "。！？!?；;…"
_HAN = re.compile(r"[一-鿿]")
_LATIN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")


def _has_han(text: str) -> bool:
    return bool(_HAN.search(text))


def _clean(text: str) -> str:
    """Strip English words and whitespace, keeping Chinese, digits and punctuation."""
    return re.sub(r"\s+", "", _LATIN.sub("", text))


def _flatten(segments: list[dict]) -> list[dict]:
    """Flatten to a word list, keeping only Mandarin-bearing words (and Chinese
    terminators used for splitting). Dropping English-only words snaps the clip
    timing to the spoken Chinese."""
    words = []
    for seg in segments:
        items = seg["words"] if seg.get("words") else [
            {"word": seg["text"], "start": seg.get("start"), "end": seg.get("end")}
        ]
        for w in items:
            if w.get("start") is None:
                continue
            if _has_han(w["word"]) or any(c in TERMINATORS for c in w["word"]):
                words.append(w)
    return words


def to_sentences(segments, audio_duration=None) -> list[dict]:
    """Split the transcript into Chinese-only sentences with tight start/end times."""
    words = _flatten(segments)
    sentences = []
    buf = []
    prev_end = None

    def flush():
        nonlocal buf
        if buf:
            text = _clean("".join(w["word"] for w in buf))
            if _has_han(text):
                sentences.append(
                    {"text": text, "start": buf[0]["start"], "end": buf[-1]["end"]}
                )
        buf = []

    for w in words:
        if buf and prev_end is not None and (w["start"] - prev_end) > MAX_GAP:
            flush()
        buf.append(w)
        prev_end = w["end"]
        stripped = w["word"].strip()
        ends_sentence = stripped and stripped[-1] in TERMINATORS
        if ends_sentence or sum(len(_clean(x["word"])) for x in buf) >= MAX_CHARS:
            flush()
    flush()

    for s in sentences:
        s["start"] = max(0.0, s["start"] - CLIP_PAD)
        s["end"] = s["end"] + CLIP_PAD
        if audio_duration:
            s["end"] = min(audio_duration, s["end"])

    return [s for s in sentences if _has_han(s["text"]) and (s["end"] - s["start"]) > 0.2]
