"""Use the Claude CLI to map the transcript into sentences and enrich them in one pass.

Given the timestamped (Mandarin-only) words, Claude chooses natural sentence boundaries
and returns each sentence's pinyin, translation, word breakdown and note. The chosen word
indices map back to precise clip start/end times. Falls back to heuristic segmentation.
"""

import concurrent.futures
import hashlib
import json
import subprocess
import tempfile

from pypinyin import Style, pinyin

from .config import CLAUDE_MODEL, CLIP_PAD, ENRICH_WORKERS
from .segment import _clean, _flatten, _has_han, to_sentences

CHUNK_WORDS = 60     # max word tokens per Claude call
CHUNK_GAP = 1.5      # also start a new chunk after a silence longer than this (seconds)

SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_index": {"type": "integer"},
                    "end_index": {"type": "integer"},
                    "chinese": {"type": "string"},
                    "pinyin": {"type": "string"},
                    "translation": {"type": "string"},
                    "words": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "hanzi": {"type": "string"},
                                "pinyin": {"type": "string"},
                                "gloss": {"type": "string"},
                            },
                            "required": ["hanzi", "pinyin", "gloss"],
                        },
                    },
                    "note": {"type": "string"},
                },
                "required": [
                    "start_index", "end_index", "chinese",
                    "pinyin", "translation", "words", "note",
                ],
            },
        }
    },
    "required": ["sentences"],
}

PROMPT = (
    "You are building Mandarin study flashcards from an auto-transcribed video. Below are "
    "Chinese word tokens, each with an index and start time in seconds. Group CONSECUTIVE "
    "tokens into natural, complete sentences a learner would study: merge fragments that "
    "belong together, and drop accidental repetition or filler. For each sentence return "
    "start_index and end_index (inclusive token indices), the chinese text, pinyin with "
    "tone marks, a natural English translation, a word-by-word breakdown, and a short note. "
    "Use the tokens in order.\n\nTokens:\n{payload}"
)


def _chunks(words):
    """Split the word stream at long pauses, capped at CHUNK_WORDS per chunk."""
    pieces, cur, prev_end = [], [], None
    for w in words:
        if cur and prev_end is not None and (w["start"] - prev_end) > CHUNK_GAP:
            pieces.append(cur)
            cur = []
        cur.append(w)
        prev_end = w["end"]
        if len(cur) >= CHUNK_WORDS:
            pieces.append(cur)
            cur = []
    if cur:
        pieces.append(cur)
    return pieces


def _call_claude(words):
    payload = "\n".join(
        f'{i}: {w["word"].strip()} (t={w["start"]:.1f})' for i, w in enumerate(words)
    )
    cmd = [
        "claude", "-p", "--model", CLAUDE_MODEL,
        "--output-format", "json", "--no-session-persistence",
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--setting-sources", "",
        "--json-schema", json.dumps(SCHEMA),
        PROMPT.format(payload=payload),
    ]
    proc = subprocess.run(
        cmd, check=True, capture_output=True, text=True, cwd=tempfile.gettempdir()
    )
    outer = json.loads(proc.stdout)
    if outer.get("is_error"):
        raise RuntimeError(outer.get("result", "claude returned an error"))
    return (outer.get("structured_output") or {}).get("sentences")


def _fallback(words):
    """Heuristic split + offline pinyin when the Claude call fails."""
    synthetic = [{
        "start": words[0]["start"], "end": words[-1]["end"],
        "text": "".join(w["word"] for w in words), "words": words,
    }]
    out = []
    for s in to_sentences(synthetic):
        s.update(
            pinyin=" ".join(p[0] for p in pinyin(s["text"], style=Style.TONE)),
            translation="", words=[], note="", fallback=True,
        )
        out.append(s)
    return out


def _process_chunk(words):
    try:
        items = _call_claude(words)
    except Exception as exc:
        print(f"  map/enrich chunk failed ({exc}); using heuristic fallback", flush=True)
        items = None

    out = []
    if items:
        n = len(words)
        for it in items:
            si, ei = it.get("start_index"), it.get("end_index")
            if not isinstance(si, int) or not isinstance(ei, int):
                continue
            si = max(0, min(si, n - 1))
            ei = max(si, min(ei, n - 1))
            text = _clean(it.get("chinese", "")) or _clean(
                "".join(w["word"] for w in words[si:ei + 1])
            )
            if not _has_han(text):
                continue
            out.append({
                "text": text,
                "start": max(0.0, words[si]["start"] - CLIP_PAD),
                "end": words[ei]["end"] + CLIP_PAD,
                "pinyin": it.get("pinyin", ""),
                "translation": it.get("translation", ""),
                "words": it.get("words", []),
                "note": it.get("note", ""),
            })

    return out or _fallback(words)


def segment_and_enrich(segments, cache_path, audio_duration=None, on_progress=None):
    """Map the transcript into enriched, Mandarin-only sentences with clip timings.

    Chunks are processed by the Claude CLI in parallel (ENRICH_WORKERS at a time) and
    cached by content hash so reruns skip finished chunks.
    """
    words = _flatten(segments)
    if not words:
        return []

    chunks = _chunks(words)
    keys = [
        hashlib.sha1("".join(w["word"] for w in c).encode("utf-8")).hexdigest()
        for c in chunks
    ]
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    results = [cache.get(k) for k in keys]
    todo = [i for i, r in enumerate(results) if r is None]
    done = len(chunks) - len(todo)

    with concurrent.futures.ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as pool:
        futures = {pool.submit(_process_chunk, chunks[i]): i for i in todo}
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            results[i] = future.result()
            cache[keys[i]] = results[i]
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
            done += 1
            if on_progress:
                on_progress(done / len(chunks))

    sentences = [s for r in results for s in (r or [])]
    if audio_duration:
        for s in sentences:
            s["end"] = min(audio_duration, s["end"])
    return sentences
