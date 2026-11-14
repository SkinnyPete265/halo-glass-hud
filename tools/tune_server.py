"""Loopback-only interactive tuning with draft rendering and explicit source application."""

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import io
import json
import os
from pathlib import Path
import threading
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import tuning


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_settings(path, settings, expected):
    values = tuning.validate(settings)
    if digest(path) != expected:
        raise ValueError("Style file changed externally. Reload before applying.")
    previous = json.loads(path.read_text(encoding="utf-8"))
    changed = [key for key in values if values[key] != previous[key]]
    if changed:
        pending = path.with_suffix(".tmp")
        pending.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
        pending.replace(path)
    native = bool(set(changed) - tuning.ART_ONLY_KEYS)
    return {
        "etag": digest(path),
        "settings": values,
        "changed": changed,
        "build": "native composition" if native else "texture-only candidate",
    }


class Preview:
    def __init__(self, root):
        self.root = root
        self.lock = threading.Lock()
        self.previous = None

    def render(self, settings, state):
        values = tuning.validate(settings)
        allowed = {"speed", "rpm", "gear", "charge", "throttle", "brake", "drs"}
        if not isinstance(state, dict) or set(state) - allowed:
            raise ValueError("Unsupported simulation fields")
        for key, limits in {
            "speed": (0, 400),
            "rpm": (0, 15000),
            "gear": (-1, 8),
            "charge": (0, 1),
            "throttle": (0, 1),
            "brake": (0, 1),
        }.items():
            value = state.get(key, 0)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not limits[0] <= value <= limits[1]
            ):
                raise ValueError("Invalid simulated " + key)
        if state.get("drs", "distance") not in ("hidden", "distance", "ready", "open"):
            raise ValueError("Invalid simulated DRS state")
        if state.get("gear", 0) != int(state.get("gear", 0)):
            raise ValueError("Gear must be a whole number")
        with self.lock:
            draft = self.root / "build/tuning/draft.json"
            draft.parent.mkdir(parents=True, exist_ok=True)
            draft.write_text(json.dumps(values), encoding="utf-8")
            os.environ["HALO_TUNING_FILE"] = str(draft)
            from halo import (
                layout,
                feature_assets,
                instruments,
                preview_instruments as hud,
            )

            importlib.reload(layout)
            importlib.reload(instruments)
            hud.static_base.cache_clear()
            if self.previous is None or any(
                self.previous[key] != values[key]
                for key in ("battery_width", "battery_height", "battery_y")
            ):
                feature_assets.battery_layers.cache_clear()
            if (
                self.previous is None
                or self.previous["rpm_width"] != values["rpm_width"]
            ):
                hud.rpm_surface.cache_clear()
            self.previous = values
            started = time.perf_counter()
            image = hud.render(hud.State(**state))
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue(), round((time.perf_counter() - started) * 1000)


def serve(root=ROOT, port=8766):
    preview = Preview(root)
    apply_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, data, content="application/json"):
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", content)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def trusted(self):
            hosts = (
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            )
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in hosts and (
                not origin or origin in ("http://" + host for host in hosts)
            )

        def do_GET(self):
            if not self.trusted():
                return self.respond(403, {"error": "Local origin required"})
            if self.path == "/":
                return self.respond(
                    200,
                    (root / "tools/tuning/index.html").read_bytes(),
                    "text/html; charset=utf-8",
                )
            if self.path == "/font":
                return self.respond(
                    200,
                    (root / "assets/fonts/Saira/Saira.ttf").read_bytes(),
                    "font/ttf",
                )
            if self.path == "/config":
                path = root / "style.json"
                return self.respond(
                    200,
                    {
                        "settings": tuning.validate(json.loads(path.read_text())),
                        "etag": digest(path),
                        "schema": tuning.schema(),
                    },
                )
            self.respond(404, {"error": "Unknown route"})

        def do_POST(self):
            if not self.trusted():
                return self.respond(403, {"error": "Local origin required"})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.respond(415, {"error": "JSON required"})
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 16384:
                    return self.respond(413, {"error": "Invalid request size"})
                data = json.loads(self.rfile.read(size))
                if self.path == "/preview":
                    image, milliseconds = preview.render(
                        data["settings"], data.get("state", {})
                    )
                    return self.respond(200, image, "image/png")
                if self.path == "/apply":
                    with apply_lock:
                        result = apply_settings(
                            root / "style.json", data["settings"], data["etag"]
                        )
                    return self.respond(200, result)
                self.respond(404, {"error": "Unknown route"})
            except (ValueError, KeyError, TypeError) as error:
                self.respond(400, {"error": str(error)})
            except Exception as error:
                self.respond(500, {"error": "Preview failed. " + str(error)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(
        json.dumps(
            {"url": f"http://127.0.0.1:{server.server_port}", "pid": os.getpid()}
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    serve(port=parser.parse_args().port)
