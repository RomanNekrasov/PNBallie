"""CPU-only regressions for experiment process isolation and private artifacts."""

import importlib.util
import json
import os
import signal
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = BACKEND_ROOT.parent / "scripts" / "avatar_experiments.py"
PROBE_SLOT = """
import sys
from app.avatar_slot import AvatarGpuBusy, gpu_slot
try:
    with gpu_slot(sys.argv[1]):
        pass
except AvatarGpuBusy:
    sys.exit(75)
"""

# Import the real supervisor, replacing only GPU work and the memory sensor.
# Its real spawned child creates a session and sleeps without importing Torch.
DRIVER = """
import importlib.util
import json
import os
import signal
import sys
import time
from pathlib import Path

module_spec = importlib.util.spec_from_file_location("experiment_under_test", RUNNER_PATH_LITERAL)
runner = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = runner
module_spec.loader.exec_module(runner)
root = Path(os.environ["PNBALLIE_EXPERIMENT_TEST_DIRECTORY"])
scenario = os.environ["PNBALLIE_EXPERIMENT_TEST_SCENARIO"]

def harmless_child(mode, spec, images, output, manifest):
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    (output / "child.pid").write_text(str(os.getpid()))
    (output / "completed-stage.txt").write_text("private completed stage")
    manifest["outputs"] = [{"file": "completed-stage.txt"}]
    runner._write_manifest(output, manifest)
    time.sleep(0.5 if scenario == "memory_recovers" else 60)
    manifest["status"] = "succeeded"
    runner._write_manifest(output, manifest)

if __name__ == "__main__":
    runner._gpu_child = harmless_child
    runner.MEMORY_SAMPLE_SECONDS = 0.05
    readings = iter([16.0, 11.0, 16.0, 11.0, 10.0] if scenario == "memory_abort"
                    else [16.0, 11.0, 16.0])
    def memory():
        if scenario.startswith("memory_") and (root / "output" / "child.pid").exists():
            return next(readings, 32.0)
        return 32.0
    runner._host_available_gib = memory
    sys.argv = [RUNNER_PATH_LITERAL, "edit", "--spec", str(root / "spec.json"),
                "--output", str(root / "output"), "--slot-lock", str(root / "gpu.lock"),
                "--timeout", "2"]
    raise SystemExit(runner.main())
"""


@pytest.fixture(scope="module")
def runner():
    module_spec = importlib.util.spec_from_file_location("avatar_experiment_artifact_test", RUNNER_PATH)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def probe_slot(path):
    return subprocess.run([sys.executable, "-c", PROBE_SLOT, str(path)], cwd=BACKEND_ROOT,
                          capture_output=True, text=True, timeout=10)


def wait_for_child(process, output):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if (output / "child.pid").is_file():
            return int((output / "child.pid").read_text())
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(f"The harmless child did not start: {stdout} {stderr}")
        time.sleep(0.01)
    pytest.fail("The harmless child did not report readiness")


@contextmanager
def experiment_process(tmp_path, scenario):
    Image.new("RGB", (64, 64), "white").save(tmp_path / "fixture.png")
    (tmp_path / "spec.json").write_text(json.dumps({
        "images": ["fixture.png"], "prompt": "PRIVATE_PORTRAIT_PROMPT_MARKER",
    }))
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER.replace("RUNNER_PATH_LITERAL", repr(str(RUNNER_PATH))))
    environment = {**os.environ, "PNBALLIE_EXPERIMENT_TEST_DIRECTORY": str(tmp_path),
                   "PNBALLIE_EXPERIMENT_TEST_SCENARIO": scenario}
    process = subprocess.Popen([sys.executable, str(driver)], cwd=BACKEND_ROOT,
                               env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        yield process, tmp_path / "output"
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                # Cleanup is restricted to this test's recorded child session.
                pid_path = tmp_path / "output" / "child.pid"
                if pid_path.is_file():
                    try:
                        os.killpg(int(pid_path.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.kill()
                process.communicate(timeout=10)


def assert_child_reaped_and_slot_available(pid, tmp_path):
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert probe_slot(tmp_path / "gpu.lock").returncode == 0


@pytest.mark.parametrize("scenario,exitcode,reason", [
    ("timeout", 1, "timeout"),
    ("termination", 128 + signal.SIGTERM, "terminated"),
])
def test_abort_reaps_real_child_releases_slot_and_retains_completed_stage(tmp_path, scenario, exitcode, reason):
    with experiment_process(tmp_path, scenario) as (process, output):
        pid = wait_for_child(process, output)
        assert probe_slot(tmp_path / "gpu.lock").returncode == 75
        if scenario == "termination":
            process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == exitcode
        manifest = json.loads((output / "manifest.json").read_text())
        assert manifest["status"] == "failed" and manifest["abort_reason"] == reason
        assert manifest["child_exitcode"] == -signal.SIGTERM
        assert manifest["outputs"] == [{"file": "completed-stage.txt"}]
        assert (output / "completed-stage.txt").read_text() == "private completed stage"
        assert_child_reaped_and_slot_available(pid, tmp_path)
        assert "PRIVATE_PORTRAIT_PROMPT_MARKER" not in stdout + stderr
        assert str(tmp_path) not in stdout + stderr
        assert not stderr
        assert stat.S_IMODE(output.stat().st_mode) == 0o700
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in output.iterdir())


@pytest.mark.parametrize("scenario,expected_status", [
    ("memory_recovers", "succeeded"), ("memory_abort", "failed"),
])
def test_low_memory_requires_consecutive_samples_and_records_private_measurements(tmp_path, scenario, expected_status):
    with experiment_process(tmp_path, scenario) as (process, output):
        pid = wait_for_child(process, output)
        process.communicate(timeout=10)
        manifest = json.loads((output / "manifest.json").read_text())
        readings = [json.loads(line)["available_gib"]
                    for line in (output / "memory.jsonl").read_text().splitlines()]
        assert manifest["status"] == expected_status
        # A recovered reading must break the first low-memory streak.
        observed = [value for value in readings if value != 32.0]
        assert observed[:3] == [16.0, 11.0, 16.0]
        if scenario == "memory_abort":
            assert observed == [16.0, 11.0, 16.0, 11.0, 10.0]
            assert manifest["abort_reason"] == "low_memory"
            assert manifest["memory"]["minimum_available_gib"] == 10.0
            assert process.returncode == 1
        else:
            assert "abort_reason" not in manifest
            assert manifest["memory"]["minimum_available_gib"] == 11.0
            assert process.returncode == 0
        assert manifest["memory"]["samples"] == len(readings)
        assert manifest["memory"]["start_available_gib"] == readings[0]
        assert manifest["memory"]["end_available_gib"] == readings[-1]
        assert manifest["memory"]["read_failures"] == 0
        assert stat.S_IMODE((output / "memory.jsonl").stat().st_mode) == 0o600
        assert_child_reaped_and_slot_available(pid, tmp_path)


def test_portrait_metadata_is_removed_alpha_is_flattened_and_outputs_cannot_overwrite_input(runner, tmp_path):
    original = Image.new("RGBA", (64, 96), (0, 0, 0, 0))
    original.putpixel((20, 30), (10, 20, 30, 255))
    original.putpixel((21, 31), (0, 0, 255, 128))
    exif = Image.Exif()
    exif[274] = 6  # Phone orientation: rotate the decoded pixels clockwise.
    exif[315] = "PRIVATE_PHOTOGRAPHER"
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Location", "PRIVATE_LOCATION")
    portrait = tmp_path / "portrait.png"
    original.save(portrait, exif=exif, pnginfo=metadata)
    original_bytes = portrait.read_bytes()
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps({"images": ["portrait.png"], "prompt": "private prompt"}))

    _, images, provenance = runner.read_spec(spec_path, "edit")
    clean = images[0]
    assert clean.mode == "RGB" and clean.size == (96, 64)
    assert clean.getpixel((0, 0)) == (255, 255, 255)
    assert clean.getpixel((65, 20)) == (10, 20, 30)
    assert clean.getpixel((64, 21)) == (127, 127, 255)
    assert not clean.info and not clean.getexif()
    assert "PRIVATE_LOCATION" not in json.dumps(provenance)
    assert "PRIVATE_PHOTOGRAPHER" not in json.dumps(provenance)

    output = tmp_path / "clean.png"
    runner._write_png(output, clean, "RGB")
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with Image.open(output) as saved:
        assert not saved.info and not saved.getexif()
    with pytest.raises(FileExistsError):
        runner._write_png(portrait, clean, "RGB")
    assert portrait.read_bytes() == original_bytes
