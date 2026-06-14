"""A small web server: serve the flashcard app and run the pipeline from the browser.

Endpoints:
  GET  /api/decks        -> list of decks (data/decks.json)
  POST /api/jobs {url}    -> queue a video, returns {id}
  GET  /api/jobs/<id>     -> job status {status, step, total, message, frac, ...}
Everything else is served as a static file from the project root.
"""

import argparse
import json
import queue
import threading
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .config import DATA_DIR, ROOT
from .run import STAGES, process

_jobs = {}
_lock = threading.Lock()
_work = queue.Queue()


def _update(job_id, **fields):
    with _lock:
        _jobs[job_id].update(fields)


def _worker():
    while True:
        job_id = _work.get()
        url = _jobs[job_id]["url"]
        _update(job_id, status="running", message="Starting")
        try:
            def on_progress(step, total, message, frac):
                _update(job_id, step=step, total=total, message=message, frac=frac)

            result = process(url, on_progress)
            _update(
                job_id, status="done", message="Done",
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
            }
        _work.put(job_id)
        return self._send_json({"id": job_id})

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
