"""Run the full pipeline: YouTube URL in, flashcard deck out."""

import argparse

from .ai_segment import segment_and_enrich
from .cards import build_cards
from .download import download_media
from .slice_media import slice_all
from .transcribe import transcribe

STAGES = 5


def process(url, on_progress=None):
    """Run every stage for one video. Returns a summary dict.

    on_progress(step, total, message, frac, detail) is called as work proceeds; `frac` is a
    0..1 fraction within the current step where available, otherwise None, and `detail` is
    optional extra text (e.g. the latest transcribed line).
    """
    def report(step, message, frac=None, detail=None):
        if on_progress:
            on_progress(step, STAGES, message, frac, detail)

    report(1, "Downloading video")
    audio_path, video_path, meta = download_media(url)
    out_dir = audio_path.parent

    report(2, "Transcribing")
    segments = transcribe(
        audio_path,
        on_progress=lambda frac, segs, words, text: report(
            2, f"Transcribing · {segs} sentences · {words} words", frac, text
        ),
    )

    report(3, "Mapping & enriching sentences")
    sentences = segment_and_enrich(
        segments, out_dir / "segment_cache.json",
        audio_duration=meta.get("duration"),
        on_progress=lambda f: report(3, "Mapping & enriching sentences", f),
    )

    report(4, f"Slicing {len(sentences)} clips")
    clip_names = slice_all(
        audio_path, video_path, sentences, out_dir / "sentences",
        on_progress=lambda f: report(4, f"Slicing {len(sentences)} clips", f),
    )

    report(5, "Writing cards")
    cards_path = build_cards(
        meta, sentences, clip_names, out_dir, has_video=video_path is not None
    )

    return {
        "video_id": meta["video_id"],
        "title": meta.get("title") or meta["video_id"],
        "count": len(sentences),
        "cards_path": str(cards_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Turn a Mandarin YouTube video into sentence flashcards."
    )
    parser.add_argument("url", help="YouTube video URL")
    args = parser.parse_args()

    last = {"step": 0}

    def prog(step, total, message, frac, detail=None):
        if step != last["step"]:
            print(f"[{step}/{total}] {message}...")
            last["step"] = step

    result = process(args.url, prog)
    print(f"Done: {result['count']} cards -> {result['cards_path']}")


if __name__ == "__main__":
    main()
