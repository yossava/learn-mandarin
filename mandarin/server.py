"""A small web server: serve the flashcard app and run the pipeline from the browser.

Endpoints:
  GET    /api/decks                  -> list of decks (data/decks.json)
  DELETE /api/decks/<id>             -> remove a deck's files and index entry
  DELETE /api/decks/<id>/cards/<n>   -> remove one card and its clips
  POST   /api/jobs {url}             -> queue a video, returns {id}
  GET    /api/jobs/<id>              -> job status {status, step, total, message, frac, ...}
Everything else is served as a static file from the project root.
"""

import argparse
import json
import queue
import shutil
import threading
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from .config import DATA_DIR, ROOT
from .run import STAGES, process

_jobs = {}
_lock = threading.Lock()
_work = queue.Queue()


def _update(job_id, **fields):
    with _lock:
        _jobs[job_id].update(fields)


def _safe_id(video_id: str) -> bool:
    return bool(video_id) and "/" not in video_id and "\\" not in video_id and not video_id.startswith(".")


def _delete_deck(video_id: str) -> bool:
    """Remove a deck's data directory and its decks.json entry. Guards against
    path traversal — only a plain directory directly under DATA_DIR is removed."""
    if not _safe_id(video_id):
        return False
    shutil.rmtree(DATA_DIR / video_id, ignore_errors=True)
    index_path = DATA_DIR / "decks.json"
    if index_path.exists():
        decks = [d for d in json.loads(index_path.read_text()) if d["id"] != video_id]
        index_path.write_text(json.dumps(decks, ensure_ascii=False, indent=2))
    return True


def _delete_card(video_id: str, card_id: int) -> dict:
    """Remove a single card from a deck and delete its clip files."""
    if not _safe_id(video_id):
        return {"ok": False}
    deck_dir = DATA_DIR / video_id
    cards_path = deck_dir / "cards.json"
    if not cards_path.exists():
        return {"ok": False}

    cards = json.loads(cards_path.read_text())
    removed = [c for c in cards if c.get("id") == card_id]
    cards = [c for c in cards if c.get("id") != card_id]
    for card in removed:
        for key in ("audio", "video"):
            rel = card.get(key)
            if not rel:
                continue
            clip = deck_dir / rel
            try:
                clip.relative_to(deck_dir)
                clip.unlink(missing_ok=True)
            except ValueError:
                pass
    cards_path.write_text(json.dumps(cards, ensure_ascii=False, indent=2))

    index_path = DATA_DIR / "decks.json"
    if index_path.exists():
        decks = json.loads(index_path.read_text())
        for d in decks:
            if d["id"] == video_id:
                d["count"] = len(cards)
        index_path.write_text(json.dumps(decks, ensure_ascii=False, indent=2))
    return {"ok": True, "count": len(cards)}


def _worker():
    while True:
        job_id = _work.get()
        url = _jobs[job_id]["url"]
        _update(job_id, status="running", message="Starting")
        try:
            def on_progress(step, total, message, frac, detail=None):
                _update(
                    job_id, step=step, total=total, message=message,
                    frac=frac, preview=detail,
                )

            result = process(url, on_progress)
            _update(
                job_id, status="done", message="Done", preview=None,
                deck_id=result["video_id"], title=result["title"], count=result["count"],
            )
        except Exception as exc:  # surface the failure to the browser
            _update(job_id, status="error", message=str(exc) or exc.__class__.__name__)
        finally:
            _work.task_done()


class Handler(SimpleHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", "/web/")
            self.end_headers()
            return
        if self.path == "/api/decks":
            path = DATA_DIR / "decks.json"
            decks = json.loads(path.read_text()) if path.exists() else []
            return self._send_json(decks)
        if self.path.startswith("/api/jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            with _lock:
                job = dict(_jobs[job_id]) if job_id in _jobs else None
            return self._send_json(job or {"error": "unknown job"}, 200 if job else 404)
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/jobs":
            return self._send_json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid request"}, 400)
        url = (data.get("url") or "").strip()
        if not url.startswith("http"):
            return self._send_json({"error": "Please paste a YouTube URL"}, 400)
        job_id = uuid.uuid4().hex[:12]
        with _lock:
            _jobs[job_id] = {
                "id": job_id, "url": url, "status": "queued",
                "step": 0, "total": STAGES, "message": "Queued", "frac": None,
                "preview": None,
            }
        _work.put(job_id)
        return self._send_json({"id": job_id})

    def do_DELETE(self):
        if not self.path.startswith("/api/decks/"):
            return self._send_json({"error": "not found"}, 404)
        rest = self.path[len("/api/decks/"):]
        if "/cards/" in rest:
            deck_part, _, card_part = rest.partition("/cards/")
            try:
                card_id = int(card_part.strip("/"))
            except ValueError:
                return self._send_json({"error": "bad card id"}, 400)
            result = _delete_card(unquote(deck_part), card_id)
            return self._send_json(result, 200 if result.get("ok") else 400)
        ok = _delete_deck(unquote(rest).strip("/"))
        return self._send_json({"ok": ok}, 200 if ok else 400)

    def log_message(self, *args):  # keep the console quiet
        pass


def main():
    parser = argparse.ArgumentParser(description="Serve the Mandarin flashcard web app.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    threading.Thread(target=_worker, daemon=True).start()
    handler = partial(Handler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Serving on http://localhost:{args.port}/web/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
