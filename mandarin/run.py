"""Run the full pipeline: YouTube URL in, flashcard deck out."""

import argparse

from .cards import build_cards
from .download import download_audio
from .enrich import enrich
from .segment import to_sentences
from .slice_audio import slice_all
from .transcribe import transcribe


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Turn a Mandarin YouTube video into sentence flashcards."
    )
    parser.add_argument("url", help="YouTube video URL")
    args = parser.parse_args()

    print("[1/6] Downloading audio...")
    audio_path, meta = download_audio(args.url)
    out_dir = audio_path.parent

    print("[2/6] Transcribing...")
    segments = transcribe(audio_path)

    print("[3/6] Splitting into sentences...")
    sentences = to_sentences(segments, audio_duration=meta.get("duration"))
    print(f"      {len(sentences)} sentences")

    print("[4/6] Slicing audio...")
    clip_names = slice_all(audio_path, sentences, out_dir / "sentences")

    print("[5/6] Enriching...")
    enriched = enrich(sentences, out_dir / "enrich_cache.json")

    print("[6/6] Writing cards.json...")
    cards_path = build_cards(meta, sentences, clip_names, enriched, out_dir)
    print(f"Done: {len(sentences)} cards -> {cards_path}")


if __name__ == "__main__":
    main()
