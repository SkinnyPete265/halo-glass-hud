"""Per-stage wall-clock measurements for local build and release diagnostics."""

import contextlib
import json
from pathlib import Path
import time


class Timings:
    def __init__(self, path):
        self.path = Path(path)
        self.stages = []

    @contextlib.contextmanager
    def stage(self, name):
        started = time.perf_counter()
        status = "failed"
        try:
            yield
            status = "passed"
        finally:
            seconds = round(time.perf_counter() - started, 3)
            self.stages.append({"stage": name, "seconds": seconds, "status": status})
            self.path.parent.mkdir(parents=True, exist_ok=True)
            pending = self.path.with_suffix(".tmp")
            pending.write_text(
                json.dumps({"stages": self.stages}, indent=2) + "\n", encoding="utf-8"
            )
            pending.replace(self.path)
            print(f"{name} {status} in {seconds:.3f}s", flush=True)
