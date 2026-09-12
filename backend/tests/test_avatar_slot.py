import base64
import os
import select
import stat
import subprocess
import sys
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import avatar_service
from app.avatar_providers import LOCAL_BUSY_HEADER
from app.avatar_slot import AvatarGpuBusy, AvatarGpuLockUnavailable, gpu_slot

BACKEND_ROOT = Path(__file__).resolve().parents[1]
HOLD_SLOT = """
import sys
from app.avatar_slot import gpu_slot
with gpu_slot(sys.argv[1]):
    print("reserved", flush=True)
    sys.stdin.read(1)
"""
PROBE_SLOT = """
import sys
from app.avatar_slot import AvatarGpuBusy, gpu_slot
try:
    with gpu_slot(sys.argv[1]):
        pass
except AvatarGpuBusy:
    sys.exit(75)
"""


@pytest.fixture
def slot_path(tmp_path, monkeypatch):
    path = tmp_path / "gpu.lock"
    monkeypatch.setenv("AVATAR_GPU_LOCK_PATH", str(path))
    return path


def probe_slot(path):
    return subprocess.run([sys.executable, "-c", PROBE_SLOT, str(path)], cwd=BACKEND_ROOT,
                          capture_output=True, text=True, timeout=10)


@contextmanager
def external_reservation(path):
    process = subprocess.Popen([sys.executable, "-c", HOLD_SLOT, str(path)], cwd=BACKEND_ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([process.stdout], [], [], 10)[0], "The reservation process did not start"
        assert process.stdout.readline().strip() == "reserved"
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=10)


def test_other_process_cannot_enter_until_owner_releases_and_file_is_retained(slot_path):
    with external_reservation(slot_path) as process:
        inode = slot_path.stat().st_ino
        assert stat.S_IMODE(slot_path.stat().st_mode) == 0o600
        with pytest.raises(AvatarGpuBusy):
            with gpu_slot():
                pytest.fail("A second process entered the reserved GPU slot")
        process.communicate(input="release", timeout=10)
        assert process.returncode == 0
    with gpu_slot():
        assert slot_path.stat().st_ino == inode
        assert probe_slot(slot_path).returncode == 75
    assert slot_path.exists()
    assert probe_slot(slot_path).returncode == 0


def test_kernel_releases_slot_after_owner_is_killed(slot_path):
    with external_reservation(slot_path) as process:
        process.kill()
        process.wait(timeout=10)
        with gpu_slot():
            assert probe_slot(slot_path).returncode == 75
    assert probe_slot(slot_path).returncode == 0


def test_exception_releases_slot_for_another_process(slot_path):
    with pytest.raises(ValueError, match="model failed"):
        with gpu_slot():
            assert probe_slot(slot_path).returncode == 75
            raise ValueError("model failed")
    assert probe_slot(slot_path).returncode == 0


def test_slot_rejects_symlinks_and_hardlinks_without_touching_target(slot_path, tmp_path):
    target = tmp_path / "unrelated"
    target.write_text("keep this")
    target.chmod(0o644)
    slot_path.symlink_to(target)
    with pytest.raises(AvatarGpuLockUnavailable):
        with gpu_slot():
            pytest.fail("The lock followed a symlink")
    slot_path.unlink()
    os.link(target, slot_path)
    with pytest.raises(AvatarGpuLockUnavailable):
        with gpu_slot():
            pytest.fail("The lock accepted a shared inode")
    assert target.read_text() == "keep this"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_slot_rejects_relative_config_and_nonregular_file(slot_path, monkeypatch):
    monkeypatch.setenv("AVATAR_GPU_LOCK_PATH", "gpu.lock")
    with pytest.raises(AvatarGpuLockUnavailable, match="absolute"):
        with gpu_slot():
            pass
    os.mkfifo(slot_path)
    with pytest.raises(AvatarGpuLockUnavailable, match="regular"):
        with gpu_slot(slot_path):
            pass


def test_service_defers_for_external_reservation_after_auth_and_recovers(slot_path, monkeypatch):
    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "service-token")
    calls = []
    image = Image.new("RGBA", (64, 64))
    ImageDraw.Draw(image).rectangle((16, 16, 48, 48), fill=(30, 200, 100, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    png = output.getvalue()

    def fake_generation(*_):
        calls.append("generate")
        # The HTTP parent keeps the cross-process lock until its child finishes.
        assert probe_slot(slot_path).returncode == 75
        return png

    monkeypatch.setattr(avatar_service, "generate_in_subprocess", fake_generation)
    client = TestClient(avatar_service.app)
    headers = {"Authorization": "Bearer service-token"}
    with external_reservation(slot_path):
        unauthorized = client.post("/v1/avatar", json={})
        assert unauthorized.status_code == 401 and LOCAL_BUSY_HEADER not in unauthorized.headers
        response = client.post("/v1/avatar", json={}, headers=headers)
        assert response.status_code == 503
        assert response.headers[LOCAL_BUSY_HEADER] == "busy"
        assert response.headers["Retry-After"] == "30"
        assert calls == []
        assert not avatar_service.generation_lock.locked()
    invalid = client.post("/v1/avatar", json={}, headers=headers)
    assert invalid.status_code == 422 and LOCAL_BUSY_HEADER not in invalid.headers
    assert probe_slot(slot_path).returncode == 0
    encoded = base64.b64encode(png).decode()
    response = client.post("/v1/avatar", json={"source_png": encoded, "reference_png": encoded},
                           headers=headers)
    assert response.status_code == 200 and calls == ["generate"]
    assert probe_slot(slot_path).returncode == 0
    assert not avatar_service.generation_lock.locked()


def test_service_lock_failure_is_unavailable_without_busy_retry_signal(slot_path, monkeypatch):
    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "service-token")
    monkeypatch.setenv("AVATAR_GPU_LOCK_PATH", str(slot_path / "missing" / "gpu.lock"))
    client = TestClient(avatar_service.app)
    response = client.post("/v1/avatar", json={}, headers={"Authorization": "Bearer service-token"})
    assert response.status_code == 503
    assert LOCAL_BUSY_HEADER not in response.headers
    assert not avatar_service.generation_lock.locked()
