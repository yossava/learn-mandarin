"""Central configuration. Any value can be overridden with an environment variable."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))

# Transcription
WHISPER_BACKEND = os.environ.get("WHISPER_BACKEND", "")  # "" = auto (MLX on Apple Silicon, else faster-whisper)
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "large-v3")   # faster-whisper (CPU) model
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")
WHISPER_MLX_MODEL = os.environ.get("WHISPER_MLX_MODEL", "mlx-community/whisper-large-v3-turbo")  # Apple GPU

# Sentence segmentation
CLIP_PAD = float(os.environ.get("CLIP_PAD", "0.15"))   # seconds added on each side of a clip
MAX_CHARS = int(os.environ.get("MAX_CHARS", "50"))     # force-split very long runs of speech
MAX_GAP = float(os.environ.get("MAX_GAP", "1.0"))      # a silence longer than this ends a sentence

# Enrichment through the Claude CLI
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "sonnet")
ENRICH_BATCH = int(os.environ.get("ENRICH_BATCH", "6"))
ENRICH_WORKERS = int(os.environ.get("ENRICH_WORKERS", "5"))  # parallel claude calls

# Video clips
WITH_VIDEO = os.environ.get("WITH_VIDEO", "1") != "0"   # set WITH_VIDEO=0 for audio only
VIDEO_HEIGHT = int(os.environ.get("VIDEO_HEIGHT", "480"))  # downscale clips to this height
