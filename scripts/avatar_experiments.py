#!/usr/bin/env python3
"""Run one private, offline Qwen experiment without changing the avatar service.

Use the existing Spark GPU image and model/cache mounts. Run from a checkout,
or supply PYTHONPATH=/app when this script is mounted beside the runtime code.

    python scripts/avatar_experiments.py edit --spec edit.json --output new-edit
    python scripts/avatar_experiments.py layered --spec layers.json --output new-layers

Edit specification (image order is significant):
    {"images": ["body.png", "portrait.png"], "prompt": "Edit image 1 ...",
     "negative_prompt": "text, checkerboard", "seed": 777,
     "width": 1024, "height": 1024, "steps": 40,
     "true_cfg_scale": 4.0, "guidance_scale": 1.0}

Layered specification:
    {"image": "new-edit/edit.png", "seed": 777, "steps": 50,
     "resolution": 640, "layers": 4, "true_cfg_scale": 4.0}

Relative image paths resolve against the specification's directory. Inputs are
decoded, EXIF-oriented, stripped of metadata, and flattened onto white for Edit.
The output directory must not exist; its parent must exist. Files are private
(0700 directory, 0600 files). The manifest contains the private prompt, input
paths/hashes, model revisions and timings; do not publish it or the pictures.
Standard output contains only bounded progress/status fields, never prompts,
paths or model exception messages. --validate-only checks inputs without a GPU
or output-directory mutation. No model download, cloud call or profile write is
performed. A supervisor holds the shared GPU slot until its fresh child exits;
the live service must use the same lock file (optionally --slot-lock PATH).
The supervisor samples host memory every five seconds into private memory.jsonl.
Two consecutive samples below 12 GiB stop only this experiment's child. Timeout,
SIGTERM and interruption also reap that child before releasing the GPU slot.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import hashlib
import json
import math
import multiprocessing
import os
import signal
import sys
import time
import warnings
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

REPOSITORY_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if REPOSITORY_BACKEND.is_dir():
    sys.path.insert(0, str(REPOSITORY_BACKEND))

MAX_SPEC_BYTES = 64 * 1024
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 16_000_000
MEMORY_SAMPLE_SECONDS = 5
MINIMUM_AVAILABLE_GIB = 12
EDIT_DEFAULTS = {
    "negative_prompt": "checkerboard, text, scenery, multiple people, cropped figure",
    "seed": 777, "width": 1024, "height": 1024, "steps": 40,
    "true_cfg_scale": 4.0, "guidance_scale": 1.0,
}
LAYERED_DEFAULTS = {
    "negative_prompt": " ", "seed": 777, "steps": 50, "resolution": 640,
    "layers": 4, "true_cfg_scale": 4.0, "cfg_normalize": True, "use_en_prompt": True,
}


class InvalidSpec(ValueError):
    """Messages are fixed diagnostics and never include private spec contents."""


def _integer(value, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidSpec(f"{name} must be an integer within {minimum}..{maximum}")
    return value


def _number(value, name: str, minimum: float, maximum: float) -> float:
    if type(value) not in {int, float} or not minimum <= value <= maximum or not math.isfinite(value):
        raise InvalidSpec(f"{name} must be finite and within {minimum}..{maximum}")
    return float(value)


def _text(value, name: str, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 8192 or (required and not value.strip()):
        raise InvalidSpec(f"{name} must be a string of at most 8192 characters")
    return value


def _read_image(path: Path, mode: str) -> tuple[Image.Image, dict]:
    if not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
        raise InvalidSpec("Each input must be a local image of at most 16 MiB")
    raw = path.read_bytes()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as opened:
                if opened.format not in {"PNG", "JPEG", "WEBP"} or getattr(opened, "n_frames", 1) != 1:
                    raise InvalidSpec("Inputs must be single-frame PNG, JPEG or WebP images")
                if min(opened.size) < 32 or opened.width * opened.height > MAX_PIXELS:
                    raise InvalidSpec("Input dimensions must be at least 32 pixels and at most 16 megapixels")
                opened.load()
                oriented = ImageOps.exif_transpose(opened).convert("RGBA")
        if mode == "edit":
            clean = Image.new("RGB", oriented.size, "white")
            clean.paste(oriented, mask=oriented.getchannel("A"))
        else:
            # Copy pixels into a fresh image to omit EXIF, ICC and text chunks.
            clean = Image.new("RGBA", oriented.size)
            clean.paste(oriented)
    except InvalidSpec:
        raise
    except Exception:
        raise InvalidSpec("An input image could not be safely decoded") from None
    normalized = BytesIO()
    clean.save(normalized, format="PNG")
    return clean, {
        "path": str(path), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "normalized_sha256": hashlib.sha256(normalized.getvalue()).hexdigest(),
        "width": clean.width, "height": clean.height, "mode": clean.mode,
    }


def read_spec(path: Path, mode: str) -> tuple[dict, list[Image.Image], list[dict]]:
    if not path.is_file() or path.stat().st_size > MAX_SPEC_BYTES:
        raise InvalidSpec("The JSON specification must be a local file of at most 64 KiB")
    try:
        raw = json.loads(path.read_text())
    except (OSError, UnicodeError, ValueError):
        raise InvalidSpec("The specification must contain valid UTF-8 JSON") from None
    if not isinstance(raw, dict):
        raise InvalidSpec("The specification must be a JSON object")
    defaults = EDIT_DEFAULTS if mode == "edit" else LAYERED_DEFAULTS
    allowed = set(defaults) | ({"images", "prompt"} if mode == "edit" else {"image"})
    if set(raw) - allowed:
        raise InvalidSpec("The specification contains unsupported fields")
    spec = {**defaults, **raw}
    _integer(spec["seed"], "seed", 0, 2**63 - 1)
    _integer(spec["steps"], "steps", 1, 100)
    spec["true_cfg_scale"] = _number(spec["true_cfg_scale"], "true_cfg_scale", 1, 10)
    _text(spec["negative_prompt"], "negative_prompt")
    if mode == "edit":
        _text(spec.get("prompt"), "prompt", required=True)
        spec["guidance_scale"] = _number(spec["guidance_scale"], "guidance_scale", 0, 10)
        for dimension in ("width", "height"):
            _integer(spec[dimension], dimension, 256, 1536)
            if spec[dimension] % 32:
                raise InvalidSpec("Output dimensions must be multiples of 32")
        paths = spec.get("images")
        if not isinstance(paths, list) or not 1 <= len(paths) <= 3:
            raise InvalidSpec("Edit requires one to three ordered input images")
    else:
        paths = [spec.get("image")]
        if type(spec["resolution"]) is not int or spec["resolution"] not in {640, 1024}:
            raise InvalidSpec("Layered resolution must be 640 or 1024")
        _integer(spec["layers"], "layers", 1, 8)
        if any(type(spec[key]) is not bool for key in ("cfg_normalize", "use_en_prompt")):
            raise InvalidSpec("Layered prompt and CFG options must be booleans")
    images, provenance = [], []
    for value in paths:
        if not isinstance(value, str) or not value or "\0" in value or "://" in value:
            raise InvalidSpec("Image inputs must be local file paths")
        candidate = Path(value).expanduser()
        resolved = (candidate if candidate.is_absolute() else path.parent / candidate).resolve()
        image, metadata = _read_image(resolved, mode)
        images.append(image)
        provenance.append(metadata)
    return spec, images, provenance


def _write_manifest(output: Path, manifest: dict) -> None:
    temporary = output / "manifest.next.json"
    with temporary.open("x", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write("\n")
    temporary.replace(output / "manifest.json")


def _write_png(path: Path, source: Image.Image, mode: str) -> dict:
    clean = Image.new(mode, source.size)
    clean.paste(source.convert(mode))
    buffer = BytesIO()
    clean.save(buffer, format="PNG")
    raw = buffer.getvalue()
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(raw)
    result = {"file": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
              "width": clean.width, "height": clean.height, "mode": clean.mode,
              "bytes": len(raw)}
    if mode == "RGBA":
        histogram = clean.getchannel("A").histogram()
        result["fully_transparent_fraction"] = histogram[0] / (clean.width * clean.height)
    return result


@contextlib.contextmanager
def _quiet_libraries():
    """Silence Python/native library diagnostics that could repeat a prompt."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = [os.dup(1), os.dup(2)]
    null = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null, 1)
        os.dup2(null, 2)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        for descriptor, original in zip((1, 2), saved, strict=True):
            os.dup2(original, descriptor)
            os.close(original)
        os.close(null)


def _gpu_child(mode: str, spec: dict, images: list[Image.Image], output: Path, manifest: dict) -> None:
    os.setsid()
    os.umask(0o077)
    for name in ("AVATAR_SERVICE_TOKEN", "OPENAI_API_KEY", "DATABASE_URL"):
        os.environ.pop(name, None)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    console = os.fdopen(os.dup(1), "w", buffering=1)
    started = time.monotonic()
    pipeline = torch = None
    stage = "initializing"

    def progress(event: str, **fields):
        console.write(json.dumps({"event": event, "stage": mode,
                                  "seconds": round(time.monotonic() - started, 3), **fields}) + "\n")

    def step_callback(_pipeline, step, _timestep, values):
        if step < 2 or (step + 1) % 5 == 0 or step + 1 == spec["steps"]:
            progress("model.progress", step=step + 1, total=spec["steps"])
        return values

    try:
        with _quiet_libraries():
            from app.avatar_service import (
                EDIT_MODEL,
                EDIT_REVISION,
                LAYERED_MODEL,
                LAYERED_REVISION,
                cuda_memory_fraction,
                foreground_from_layers,
                require_capacity,
            )
            require_capacity()
            import torch
            from diffusers import QwenImageEditPlusPipeline, QwenImageLayeredPipeline

            if not torch.cuda.is_available():
                raise RuntimeError("CUDA unavailable")
            fraction = min(cuda_memory_fraction(), 0.70)
            torch.cuda.set_per_process_memory_fraction(fraction)
            manifest["cuda_memory_fraction"] = fraction
            manifest["runtime"] = {"torch": torch.__version__, "cuda": torch.version.cuda}
            model, revision = (EDIT_MODEL, EDIT_REVISION) if mode == "edit" else (LAYERED_MODEL, LAYERED_REVISION)
            manifest["model"] = {"id": model, "revision": revision, "dtype": "bfloat16", "offline": True}
            stage = "loading"
            progress("model.loading")
            load_started = time.monotonic()
            pipeline_class = QwenImageEditPlusPipeline if mode == "edit" else QwenImageLayeredPipeline
            pipeline = pipeline_class.from_pretrained(
                model, revision=revision, torch_dtype=torch.bfloat16, local_files_only=True,
                device_map="cuda", low_cpu_mem_usage=True,
            )
            pipeline.set_progress_bar_config(disable=True)
            manifest["timings"]["load_seconds"] = round(time.monotonic() - load_started, 3)
            progress("model.loaded", duration_seconds=manifest["timings"]["load_seconds"])
            _write_manifest(output, manifest)
            stage = "inference"
            inference_started = time.monotonic()
            arguments = {
                "generator": torch.Generator(device="cuda").manual_seed(spec["seed"]),
                "negative_prompt": spec["negative_prompt"], "true_cfg_scale": spec["true_cfg_scale"],
                "num_inference_steps": spec["steps"], "num_images_per_prompt": 1,
                "callback_on_step_end": step_callback, "callback_on_step_end_tensor_inputs": [],
            }
            if mode == "edit":
                arguments.update(image=images, prompt=spec["prompt"], width=spec["width"],
                                 height=spec["height"], guidance_scale=spec["guidance_scale"])
            else:
                arguments.update(image=images[0], resolution=spec["resolution"], layers=spec["layers"],
                                 cfg_normalize=spec["cfg_normalize"], use_en_prompt=spec["use_en_prompt"])
            with torch.inference_mode():
                generated = pipeline(**arguments).images[0]
            manifest["timings"]["inference_seconds"] = round(time.monotonic() - inference_started, 3)
            stage = "saving"
            if mode == "edit":
                manifest["outputs"].append(_write_png(output / "edit.png", generated, "RGB"))
            else:
                # Keep every original layer even if conservative composition rejects it.
                for index, layer in enumerate(generated):
                    manifest["outputs"].append(_write_png(output / f"layer-{index:02d}.png", layer, "RGBA"))
                _write_manifest(output, manifest)
                foreground = foreground_from_layers(generated)
                with Image.open(BytesIO(foreground)) as image:
                    manifest["outputs"].append(_write_png(output / "foreground.png", image, "RGBA"))
            manifest["status"] = "succeeded"
            progress("experiment.saved", outputs=len(manifest["outputs"]))
    except BaseException as error:
        manifest.update(status="failed", error={"type": type(error).__name__, "stage": stage})
        progress("experiment.failed", error_type=type(error).__name__, failed_stage=stage)
    finally:
        with _quiet_libraries():
            del pipeline
            gc.collect()
            if torch is not None and torch.cuda.is_initialized():
                torch.cuda.empty_cache()
        manifest["timings"]["child_seconds"] = round(time.monotonic() - started, 3)
        _write_manifest(output, manifest)
        progress("model.released")
        console.close()
    raise SystemExit(0 if manifest["status"] == "succeeded" else 1)


def _stop_child(child) -> None:
    if not child.is_alive():
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        # Spawn may still be importing/deserializing before its setsid call.
        child.terminate()
    child.join(10)
    if child.is_alive():
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            child.kill()
        child.join(10)


def _host_available_gib() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024**2
    except (OSError, ValueError, IndexError):
        pass
    return None


def _sigterm(_signum, _frame) -> None:
    # The supervisor's exception path must reap the child before slot release.
    raise SystemExit(128 + signal.SIGTERM)


def _supervise_child(child, output: Path, started: float, timeout: int) -> tuple[dict, str | None, BaseException | None]:
    summary = {"file": "memory.jsonl", "sample_interval_seconds": MEMORY_SAMPLE_SECONDS,
               "abort_below_gib": MINIMUM_AVAILABLE_GIB, "consecutive_low_samples_required": 2,
               "samples": 0, "read_failures": 0, "start_available_gib": None,
               "end_available_gib": None, "minimum_available_gib": None}
    reason = interruption = None
    consecutive_low = 0
    with (output / "memory.jsonl").open("x", encoding="utf-8") as stream:
        os.chmod(output / "memory.jsonl", 0o600)

        def sample() -> float | None:
            available = _host_available_gib()
            stream.write(json.dumps({"timestamp": datetime.now(UTC).isoformat(),
                                     "seconds": round(time.monotonic() - started, 3),
                                     "available_gib": available}) + "\n")
            stream.flush()
            if summary["samples"] == 0:
                summary["start_available_gib"] = available
            summary["samples"] += 1
            summary["end_available_gib"] = available
            if available is None:
                summary["read_failures"] += 1
            else:
                minimum = summary["minimum_available_gib"]
                summary["minimum_available_gib"] = available if minimum is None else min(minimum, available)
            return available

        try:
            available = sample()
            consecutive_low = int(available is not None and available < MINIMUM_AVAILABLE_GIB)
            child.start()
            while child.is_alive():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    reason = "timeout"
                    break
                child.join(min(MEMORY_SAMPLE_SECONDS, remaining))
                available = sample()
                consecutive_low = consecutive_low + 1 if available is not None and available < MINIMUM_AVAILABLE_GIB else 0
                if child.is_alive() and consecutive_low >= 2:
                    reason = "low_memory"
                    break
        except BaseException as error:
            interruption = error
            reason = "terminated" if isinstance(error, SystemExit) else "interrupted"
        finally:
            if reason is not None:
                _stop_child(child)
            sample()
    return summary, reason, interruption


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("edit", "layered"))
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--slot-lock", type=Path, help="Shared private GPU lock; defaults to service configuration")
    parser.add_argument("--timeout", type=int, default=3600, help="Maximum child runtime in seconds (default: 3600)")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    signal.signal(signal.SIGTERM, _sigterm)
    try:
        _integer(args.timeout, "timeout", 1, 7200)
        spec, images, inputs = read_spec(args.spec.resolve(), args.mode)
        if args.slot_lock is not None and not args.slot_lock.is_absolute():
            raise InvalidSpec("The shared lock path must be absolute")
        if args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir():
            raise InvalidSpec("The output directory must be new and its parent must exist")
    except (InvalidSpec, OSError) as error:
        parser.error(str(error) if isinstance(error, InvalidSpec) else "Local input/output validation failed")
    if args.validate_only:
        print(json.dumps({"event": "spec.validated", "stage": args.mode, "inputs": len(images)}), flush=True)
        return 0

    from app.avatar_slot import AvatarGpuBusy, AvatarGpuLockUnavailable, gpu_slot

    output = args.output.resolve()
    manifest = {"schema_version": 1, "mode": args.mode, "status": "running",
                "started_at": datetime.now(UTC).isoformat(), "specification": spec,
                "inputs": inputs, "outputs": [], "timings": {}, "timeout_seconds": args.timeout}
    try:
        with gpu_slot(path=args.slot_lock):
            output.mkdir(mode=0o700)
            _write_manifest(output, manifest)
            child = multiprocessing.get_context("spawn").Process(
                target=_gpu_child, args=(args.mode, spec, images, output, manifest),
                name="pnballie-avatar-experiment",
            )
            started = time.monotonic()
            memory, reason, interruption = _supervise_child(child, output, started, args.timeout)
            manifest = json.loads((output / "manifest.json").read_text())
            manifest["timings"]["supervisor_seconds"] = round(time.monotonic() - started, 3)
            manifest["child_exitcode"] = child.exitcode
            manifest["memory"] = memory
            if reason is not None or child.exitcode != 0:
                manifest["status"] = "failed"
                if reason is not None:
                    error_type = {"timeout": "TimeoutError", "low_memory": "LowMemoryError",
                                  "terminated": "SystemExit", "interrupted": "InterruptedError"}[reason]
                    manifest["error"] = {"type": error_type, "stage": "supervisor"}
                    manifest["abort_reason"] = reason
                elif "error" not in manifest:
                    manifest["error"] = {"type": "ChildProcessError", "stage": "supervisor"}
            manifest["finished_at"] = datetime.now(UTC).isoformat()
            _write_manifest(output, manifest)
            print(json.dumps({"event": "experiment.finished", "stage": args.mode,
                              "status": manifest["status"], "child_exitcode": child.exitcode,
                              "seconds": manifest["timings"]["supervisor_seconds"]}), flush=True)
            if interruption is not None:
                raise interruption
            return 0 if manifest["status"] == "succeeded" else 1
    except (AvatarGpuBusy, AvatarGpuLockUnavailable) as error:
        print(json.dumps({"event": "experiment.unavailable", "error_type": type(error).__name__}), flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
