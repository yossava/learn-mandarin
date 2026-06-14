"""Assemble the final cards.json and keep the deck index up to date."""

import json
from pathlib import Path

from .config import DATA_DIR


def build_cards(meta, sentences, clip_names, enriched, out_dir: Path) -> Path:
    cards = []
    for i, (s, name, e) in enumerate(zip(sentences, clip_names, enriched), 1):
        cards.append(
            {
                "id": i,
                "audio": f"sentences/{name}",
                "chinese": s["text"],
                "pinyin": e.get("pinyin", ""),
                "translation": e.get("translation", ""),
                "words": e.get("words", []),
                "note": e.get("note", ""),
                "start": round(s["start"], 3),
                "end": round(s["end"], 3),
                "source": {
                    "title": meta.get("title"),
                    "video_id": meta.get("video_id"),
                    "url": meta.get("url"),
                    "channel": meta.get("channel"),
                },
            }
        )

    cards_path = out_dir / "cards.json"
    cards_path.write_text(json.dumps(cards, ensure_ascii=False, indent=2))
    _update_index(meta, len(cards))
    return cards_path


def _update_index(meta, count: int) -> None:
    index_path = DATA_DIR / "decks.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    decks = json.loads(index_path.read_text()) if index_path.exists() else []
    decks = [d for d in decks if d["id"] != meta["video_id"]]
    decks.append(
        {
            "id": meta["video_id"],
            "title": meta.get("title") or meta["video_id"],
            "count": count,
            "source_url": meta.get("url"),
        }
    )
    index_path.write_text(json.dumps(decks, ensure_ascii=False, indent=2))
