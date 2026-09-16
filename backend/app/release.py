"""Public release identity and a private worker liveness heartbeat."""
import json
import os
import threading
import time
from pathlib import Path


def worker_revision():
    try:
        path = Path(os.environ["AVATAR_WORKER_HEARTBEAT_PATH"])
        if path.stat().st_size > 1024:
            return None
        value = json.loads(path.read_text())
        if 0 <= time.time() - value["time"] < 60:
            return value["revision"]
    except (KeyError, OSError, ValueError, TypeError):
        pass
    return None


class WorkerHeartbeat:
    def __init__(self):
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stopped.is_set():
            try:
                path = Path(os.environ["AVATAR_WORKER_HEARTBEAT_PATH"])
                temporary = path.with_suffix(".tmp")
                temporary.write_text(json.dumps({
                    "revision": os.getenv("APP_REVISION", "development"), "time": time.time(),
                }))
                temporary.chmod(0o600)
                temporary.replace(path)
            except OSError:
                pass
            self.stopped.wait(10)

    def start(self):
        if os.getenv("AVATAR_WORKER_HEARTBEAT_PATH"):
            self.thread.start()

    def stop(self):
        self.stopped.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2)
