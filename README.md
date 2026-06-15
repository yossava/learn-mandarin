# learn-mandarin

Turn Mandarin YouTube videos into per-sentence audio flashcards.

Give it a YouTube URL and it downloads the audio, transcribes it with Whisper, splits the
transcript into sentences, cuts an MP3 clip for each one, and adds pinyin, an English
translation and a word-by-word breakdown. The result is a JSON deck plus an audio folder
you study in the bundled web app — where you can also paste new URLs and watch them process.

## How it works

The run is a six-stage pipeline (`mandarin/run.py`):

1. **download** — fetch the video with audio via yt-dlp (capped at 480p)
2. **transcribe** — Whisper with word-level timestamps (Apple-Silicon GPU via mlx-whisper when installed, otherwise faster-whisper on CPU)
3. **map & enrich** — the `claude` CLI groups the Mandarin words into natural sentences and adds pinyin, translation and a word breakdown in one pass (English is dropped)
4. **slice** — cut one video clip (mp4, with sound) per sentence with ffmpeg
5. **cards** — write `cards.json` and update the deck index

Each stage caches its output under `data/<video_id>/`, so re-running skips work that is
already done.

## Requirements

- Python 3.13
- ffmpeg (`brew install ffmpeg`)
- deno (`brew install deno`) — yt-dlp uses it to solve YouTube's JavaScript challenges
- The [`claude`](https://docs.claude.com/en/docs/claude-code) CLI, logged in — used for enrichment (no API key needed)
- On Apple Silicon, optionally `pip install mlx-whisper` — transcription then runs on the GPU (~6× faster, auto-selected)

## Setup

```sh
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Web app

Run everything from the browser — add lessons, watch them process, and study:

```sh
python3 -m mandarin.server
```

Open <http://localhost:8000/web/>, paste a Mandarin YouTube URL, and click **Add lesson**.
A progress bar tracks the six stages; when it finishes the new lesson appears in the picker.
**Delete** removes the selected lesson and all its files. Studying:

- `Space` — play audio
- `←` / `→` — previous / next card
- `F` — flip
- `1` / `2` — mark again / known

Progress is stored in the browser. Use a video that is **spoken in Mandarin** — an
English-narrated lesson is transcribed as English.

## Command line

You can also process a video without the server:

```sh
python3 -m mandarin.run "https://www.youtube.com/watch?v=..."
```

Output is written to `data/<video_id>/`:

- `video.mp4` / `audio.mp3` — the downloaded video and its extracted audio
- `sentences/0001.mp4` — one clip (with sound) per sentence; `.mp3` instead when `WITH_VIDEO=0`
- `cards.json` — the deck (see below)

## Configuration

Override any default with an environment variable (applies to both the server and the CLI):

| Variable | Default | Description |
| --- | --- | --- |
| `WHISPER_BACKEND` | auto | `mlx` (Apple GPU) or `faster-whisper` (CPU); auto-picks MLX when installed. |
| `WHISPER_MLX_MODEL` | `…large-v3-turbo` | MLX model repo used by the GPU backend. |
| `WHISPER_MODEL` | `large-v3` | faster-whisper (CPU) model. `medium` / `small` are faster and lighter. |
| `WHISPER_DEVICE` | `cpu` | faster-whisper device. |
| `WHISPER_COMPUTE` | `int8` | Compute type. |
| `CLAUDE_MODEL` | `sonnet` | Model used for enrichment. |
| `ENRICH_BATCH` | `6` | Sentences sent to the `claude` CLI per call. |
| `ENRICH_WORKERS` | `5` | Enrichment calls to run in parallel (lower if rate-limited). |
| `CLIP_PAD` | `0.15` | Seconds of padding added to each side of a clip. |
| `MAX_CHARS` | `50` | Force a sentence split after this many characters. |
| `MAX_GAP` | `1.0` | A silence longer than this (seconds) ends a sentence. |
| `WITH_VIDEO` | `1` | Set to `0` to skip video and produce audio-only clips. |
| `VIDEO_HEIGHT` | `480` | Max height (px) for the downloaded video and clips. |

On Apple Silicon, install `mlx-whisper` and transcription runs on the GPU (~6× faster than
CPU), auto-selected. Without it, faster-whisper runs on CPU where `large-v3` is accurate but
slow — use `WHISPER_MODEL=small` (or `medium`) to speed that up:

```sh
pip install mlx-whisper                           # Apple-Silicon GPU transcription
WHISPER_MODEL=small python3 -m mandarin.server    # or speed up the CPU backend
```

## Card format

```json
{
  "id": 1,
  "video": "sentences/0001.mp4",
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
