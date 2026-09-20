"""The local 3D viewer: serves viewer/ and the flies' replays on localhost."""

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import FLIES, ROOT, fly_ids, load_fly

VIEWER = ROOT / "viewer"


def manifest() -> dict[str, dict]:
    """What the page needs to list the flies: name, market, schedule, and the last known equity."""
    out = {}
    for fly_id in fly_ids():
        c = load_fly(fly_id)
        out[fly_id] = {"name": c["name"], "universe": c["universe"], "cadence": c["cadence"], "bot_id": c.get("bot_id"),
                       "equity": c.get("equity"), "return_pct": c.get("return_pct")}
    return out


class Handler(SimpleHTTPRequestHandler):
    """Files under /flies/ come from the flies folder. Everything else comes from viewer/."""

    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/flies/"):
            target = (FLIES / clean[len("/flies/"):]).resolve()
            # Only replays and positions are served. Keys are never in this folder, and fly.json stays private.
            allowed = target.is_relative_to(FLIES.resolve()) and (target.parent.name == "replays" or target.name == "positions.json")
            return str(target) if allowed else str(VIEWER / "missing")
        return super().translate_path(path)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/flies/flies.json":
            body = json.dumps(manifest()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, format: str, *args: object) -> None:
        pass


def serve(port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(VIEWER)))
    print(f"the fly is at http://localhost:{port}  (Ctrl+C to stop)")
    server.serve_forever()
