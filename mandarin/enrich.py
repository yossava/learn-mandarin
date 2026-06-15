"""Add pinyin, translation and a word breakdown to each sentence via the Claude CLI."""

import concurrent.futures
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from pypinyin import Style, pinyin

from .config import CLAUDE_MODEL, ENRICH_BATCH, ENRICH_WORKERS

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
    # Keep each call lean: no MCP servers and no project/CLAUDE.md context, run from a
    # temp dir. Otherwise every call reloads the whole environment and crawls.
    cmd = [
        "claude", "-p",
        "--model", CLAUDE_MODEL,
        "--output-format", "json",
        "--no-session-persistence",
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


def _enrich_batch(batch: list[dict]):
    texts = [s["text"] for s in batch]
    try:
        items = _call_claude(texts)
    except Exception as exc:
        print(f"  enrichment batch failed ({exc}); using pinyin fallback", flush=True)
        items = None
    if items is None:
        items = [_fallback(t) for t in texts]
    return batch, items


def enrich(sentences: list[dict], cache_path: Path, on_progress=None) -> list[dict]:
    """Enrich every sentence, caching by text hash so reruns skip finished work.

    Batches are sent to the Claude CLI in parallel (ENRICH_WORKERS at a time).
    on_progress, if given, is called with a 0..1 fraction as batches finish.
    """
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo = [s for s in sentences if _key(s["text"]) not in cache]

    if todo:
        batches = [todo[i : i + ENRICH_BATCH] for i in range(0, len(todo), ENRICH_BATCH)]
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as pool:
            futures = [pool.submit(_enrich_batch, b) for b in batches]
            for future in concurrent.futures.as_completed(futures):
                batch, items = future.result()
                for s, item in zip(batch, items):
                    cache[_key(s["text"])] = item
                done += len(batch)
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
                if on_progress:
                    on_progress(min(1.0, done / len(todo)))
    elif on_progress:
        on_progress(1.0)

    return [cache[_key(s["text"])] for s in sentences]
