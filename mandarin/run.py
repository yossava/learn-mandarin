"""Run the full pipeline: YouTube URL in, flashcard deck out."""

import argparse

from .cards import build_cards
from .download import download_audio
from .enrich import enrich
from .segment import to_sentences
from .slice_audio import slice_all
from .transcribe import transcribe

STAGES = 6


def process(url, on_progress=None):
    """Run every stage for one video. Returns a summary dict.

    on_progress(step, total, message, frac) is called as work proceeds; `frac` is a
    0..1 fraction within the current step where available, otherwise None.
    """
    def report(step, message, frac=None):
        if on_progress:
            on_progress(step, STAGES, message, frac)

    report(1, "Downloading audio")
    audio_path, meta = download_audio(url)
    out_dir = audio_path.parent

    report(2, "Transcribing")
    segments = transcribe(audio_path, on_progress=lambda f: report(2, "Transcribing", f))

    report(3, "Splitting into sentences")
    sentences = to_sentences(segments, audio_duration=meta.get("duration"))

    report(4, f"Slicing {len(sentences)} clips")
    clip_names = slice_all(audio_path, sentences, out_dir / "sentences")

    report(5, "Enriching")
    enriched = enrich(
        sentences, out_dir / "enrich_cache.json",
        on_progress=lambda f: report(5, "Enriching", f),
    )

    report(6, "Writing cards")
    cards_path = build_cards(meta, sentences, clip_names, enriched, out_dir)

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

    def prog(step, total, message, frac):
        if step != last["step"]:
            print(f"[{step}/{total}] {message}...")
            last["step"] = step

    result = process(args.url, prog)
    print(f"Done: {result['count']} cards -> {result['cards_path']}")


if __name__ == "__main__":
    main()
