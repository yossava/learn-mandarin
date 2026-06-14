# learn-mandarin

Turn Mandarin YouTube videos into per-sentence audio flashcards.

Give it a YouTube URL and it downloads the audio, transcribes it with Whisper, splits the
transcript into sentences, cuts an MP3 clip for each one, and adds pinyin, an English
translation and a word-by-word breakdown. The result is a JSON deck plus an audio folder
you study in the bundled web app — where you can also paste new URLs and watch them process.

## How it works

The run is a six-stage pipeline (`mandarin/run.py`):

1. **download** — pull the audio as mp3 with yt-dlp
2. **transcribe** — faster-whisper, with word-level timestamps
3. **segment** — group words into sentences on punctuation and pauses
4. **slice** — cut one mp3 per sentence with ffmpeg
5. **enrich** — pinyin, translation and word breakdown via the `claude` CLI
6. **cards** — write `cards.json` and update the deck index

Each stage caches its output under `data/<video_id>/`, so re-running skips work that is
already done.

## Requirements

- Python 3.13
- ffmpeg (`brew install ffmpeg`)
- The [`claude`](https://docs.claude.com/en/docs/claude-code) CLI, logged in — used for enrichment (no API key needed)

Optional: install `deno` so yt-dlp has a JavaScript runtime for YouTube extraction.

## Setup

```sh
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Web app

Run everything from the browser — add lessons, watch them process, and study:

```sh
python -m mandarin.server
```

Open <http://localhost:8000/web/>, paste a Mandarin YouTube URL, and click **Add lesson**.
A progress bar tracks the six stages; when it finishes the new lesson appears in the picker.
Studying:

- `Space` — play audio
- `←` / `→` — previous / next card
- `F` — flip
- `1` / `2` — mark again / known

Progress is stored in the browser. Use a video that is **spoken in Mandarin** — an
English-narrated lesson is transcribed as English.

## Command line

You can also process a video without the server:

```sh
python -m mandarin.run "https://www.youtube.com/watch?v=..."
```

Output is written to `data/<video_id>/`:

- `audio.mp3` — extracted audio
- `sentences/0001.mp3 …` — one clip per sentence
- `cards.json` — the deck (see below)

## Configuration

Override any default with an environment variable (applies to both the server and the CLI):

| Variable | Default | Description |
| --- | --- | --- |
| `WHISPER_MODEL` | `large-v3` | Whisper model. `medium` / `small` are faster and lighter. |
| `WHISPER_DEVICE` | `cpu` | faster-whisper device. |
| `WHISPER_COMPUTE` | `int8` | Compute type. |
| `CLAUDE_MODEL` | `sonnet` | Model used for enrichment. |
| `ENRICH_BATCH` | `20` | Sentences sent to the `claude` CLI per call. |
| `CLIP_PAD` | `0.15` | Seconds of padding added to each side of a clip. |
| `MAX_CHARS` | `50` | Force a sentence split after this many characters. |
| `MAX_GAP` | `1.0` | A silence longer than this (seconds) ends a sentence. |

The first run downloads the Whisper model (`large-v3` is ~3 GB, `small` ~0.5 GB). On Apple
Silicon faster-whisper runs on CPU, so `large-v3` is the most accurate but slow — `small`
is handy while trying things out:

```sh
WHISPER_MODEL=small python -m mandarin.server
```

## Card format

```json
{
  "id": 1,
  "audio": "sentences/0001.mp3",
  "chinese": "大橘想吃披萨,叮咚,门铃响了。",
  "pinyin": "Dà jú xiǎng chī pīsà, dīng dōng, mén líng xiǎng le.",
  "translation": "Big Orange wants to eat pizza — ding-dong, the doorbell rings.",
  "words": [{ "hanzi": "大橘", "pinyin": "Dà jú", "gloss": "Big Orange (name)" }],
  "note": "叮咚 is the onomatopoeia for a doorbell.",
  "start": 0.0,
  "end": 7.02,
  "source": { "title": "...", "video_id": "...", "url": "...", "channel": "..." }
}
```

## Layout

```
mandarin/   pipeline package, one module per stage, plus the web server
web/        static flashcard app
data/       generated audio and decks (gitignored)
```
