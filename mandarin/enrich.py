"""Add pinyin, translation and a word breakdown to each sentence via the Claude CLI."""

import hashlib
import json
import subprocess
from pathlib import Path

from pypinyin import Style, pinyin

from .config import CLAUDE_MODEL, ENRICH_BATCH

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
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
                "required": ["pinyin", "translation", "words", "note"],
            },
        }
    },
    "required": ["items"],
}

PROMPT = (
    "You are building Mandarin study flashcards. For each Chinese sentence below, give the "
    "pinyin (with tone marks), a natural English translation, a word-by-word breakdown "
    "(hanzi, pinyin, short gloss), and a brief usage note or mnemonic. Return the results "
    "in the items array in the SAME ORDER as the input.\n\nSentences:\n{payload}"
)


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _fallback(text: str) -> dict:
    """Offline pinyin only, used when the Claude call fails."""
    syllables = [p[0] for p in pinyin(text, style=Style.TONE)]
    return {
        "pinyin": " ".join(syllables),
        "translation": "",
        "words": [],
        "note": "",
        "fallback": True,
    }


def _call_claude(texts: list[str]) -> list[dict] | None:
    payload = json.dumps(
        [{"index": i, "chinese": t} for i, t in enumerate(texts)], ensure_ascii=False
    )
    cmd = [
        "claude", "-p",
        "--model", CLAUDE_MODEL,
        "--output-format", "json",
        "--no-session-persistence",
        "--json-schema", json.dumps(SCHEMA),
        PROMPT.format(payload=payload),
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    outer = json.loads(proc.stdout)
    if outer.get("is_error"):
        raise RuntimeError(outer.get("result", "claude returned an error"))

    # With --json-schema the validated payload is in `structured_output`;
    # `result` is left empty. Fall back to parsing `result` just in case.
    data = outer.get("structured_output")
    if data is None:
        raw = outer.get("result") or ""
        data = json.loads(raw) if raw else {}
    items = data.get("items")
    if not items or len(items) != len(texts):
        return None
    return items


def enrich(sentences: list[dict], cache_path: Path) -> list[dict]:
    """Enrich every sentence, caching by text hash so reruns skip finished work."""
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    todo = [s for s in sentences if _key(s["text"]) not in cache]
    for i in range(0, len(todo), ENRICH_BATCH):
        batch = todo[i : i + ENRICH_BATCH]
        texts = [s["text"] for s in batch]
        try:
            items = _call_claude(texts)
        except Exception as exc:
            print(f"  enrichment batch failed ({exc}); using pinyin fallback", flush=True)
            items = None
        if items is None:
            items = [_fallback(t) for t in texts]
        for s, item in zip(batch, items):
            cache[_key(s["text"])] = item
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    return [cache[_key(s["text"])] for s in sentences]
