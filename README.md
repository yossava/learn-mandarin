# learn-mandarin

Turn Mandarin YouTube videos into per-sentence audio flashcards.

The pipeline downloads a video's audio, transcribes it with Whisper, splits it into
sentences, cuts an MP3 clip for each one, and adds pinyin, an English translation and a
word-by-word breakdown. The result is a JSON deck plus an audio folder you can study in
the bundled web app.

## Requirements

- Python 3.13
- ffmpeg
- The [`claude`](https://docs.claude.com/en/docs/claude-code) CLI (used for sentence enrichment)

## Setup

```sh
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```sh
python -m mandarin.run "https://www.youtube.com/watch?v=..."
```

Output is written to `data/<video_id>/`:

- `audio.mp3` — extracted audio
- `sentences/0001.mp3 …` — one clip per sentence
- `cards.json` — Chinese text, pinyin, translation, word breakdown and timings

The transcription model defaults to `large-v3`. For a faster, lighter run set
`WHISPER_MODEL=medium` (or `small`).

## Study

```sh
python -m http.server 8000
```

Open <http://localhost:8000/web/> and pick a deck.

- `Space` — play audio
- `←` / `→` — previous / next card
- `F` — flip
- `1` / `2` — mark again / known

Progress is stored in the browser.
