import json
import time

from app.release import WorkerHeartbeat, worker_revision


def test_worker_heartbeat_identifies_live_worker_only(tmp_path, monkeypatch):
    path = tmp_path / "worker.json"
    monkeypatch.setenv("AVATAR_WORKER_HEARTBEAT_PATH", str(path))
    monkeypatch.setenv("APP_REVISION", "a" * 40)
    assert worker_revision() is None
    heartbeat = WorkerHeartbeat()
    heartbeat.start()
    try:
        for _ in range(100):
            if worker_revision():
                break
            time.sleep(.01)
        assert worker_revision() == "a" * 40
    finally:
        heartbeat.stop()
    path.write_text(json.dumps({"revision": "old", "time": time.time() - 61}))
    assert worker_revision() is None
    path.write_text("bad")
    assert worker_revision() is None
