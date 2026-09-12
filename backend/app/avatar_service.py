"""Optional, private Spark inference service (install the ``avatar-gpu`` extra).

Model weights must be provisioned separately. The HTTP process stays lightweight
and launches one child per request. Models load sequentially; child exit releases
remaining CUDA runtime state. The web API needs no Kubernetes scaling credentials.
"""

import base64
import binascii
import gc
import hmac
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from PIL import Image
from starlette.concurrency import run_in_threadpool

from app.avatar_images import (
    MAX_OUTPUT_BYTES,
    MAX_UPLOAD_BYTES,
    InvalidAvatarImage,
    normalize_upload,
    remove_alpha_noise,
    validate_transparent_png,
)
from app.avatar_providers import (
    AVATAR_PROMPT,
    LOCAL_BUSY_HEADER,
    LOCAL_BUSY_RETRY_SECONDS,
)
from app.telemetry import (
    INFERENCE_SERVICE,
    Runtime,
    current_traceparent,
    event,
    install_http,
    operation_span,
    span_result,
)

telemetry = Runtime(INFERENCE_SERVICE)


@asynccontextmanager
async def lifespan(_):
    telemetry.configure()
    try:
        yield
    finally:
        telemetry.close()

EDIT_MODEL = "Qwen/Qwen-Image-Edit-2511"
EDIT_REVISION = "6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9"
LAYERED_MODEL = "Qwen/Qwen-Image-Layered"
LAYERED_REVISION = "8f0ca708dfff6ba1dd5f2d85d78f8c108a040bcf"

app = FastAPI(title="PNBallie private avatar inference", docs_url=None, redoc_url=None,
              openapi_url=None, lifespan=lifespan)
generation_lock = threading.Lock()


class InferenceUnavailable(RuntimeError):
    pass


def require_capacity() -> None:
    """Spark uses unified memory; nvidia-smi reports memory as N/A on this host."""
    minimum = float(os.getenv("AVATAR_MIN_AVAILABLE_GIB", "80")) * 1024 ** 3
    try:
        meminfo = Path("/proc/meminfo").read_text()
        available = next(int(line.split()[1]) * 1024 for line in meminfo.splitlines()
                         if line.startswith("MemAvailable:"))
    except (OSError, StopIteration, ValueError) as exc:
        raise InferenceUnavailable("Spark memory capacity cannot be verified") from exc
    if available < minimum:
        raise InferenceUnavailable("Insufficient available memory for avatar inference")


def cuda_memory_fraction() -> float:
    try:
        fraction = float(os.getenv("AVATAR_CUDA_MEMORY_FRACTION", "0.70"))
    except ValueError:
        raise InferenceUnavailable("AVATAR_CUDA_MEMORY_FRACTION must be finite and within (0, 1]") from None
    if not math.isfinite(fraction) or not 0 < fraction <= 1:
        raise InferenceUnavailable("AVATAR_CUDA_MEMORY_FRACTION must be finite and within (0, 1]")
    return fraction


def foreground_from_layers(layers: list[Image.Image]) -> bytes:
    """Compose transparent foreground layers; reject opaque or edge-filling ones.

    A Qwen-Layered output can separate head, body and ball into multiple layers.
    Selecting just the first transparent layer could lose part of the player.
    Border transparency is a conservative check for our centered, margin-framed
    sprite. Visual likeness/quality still needs the real GPU acceptance test.
    """
    if not layers or len(layers) > 12:
        raise InvalidAvatarImage("Het model gaf geen bruikbare lagen terug.")
    size = layers[0].size
    foreground = Image.new("RGBA", size)
    selected = 0
    for layer in layers:
        if layer.size != size or layer.mode != "RGBA":
            raise InvalidAvatarImage("Het model gaf geen consistente RGBA-lagen terug.")
        alpha = layer.getchannel("A")
        histogram = alpha.histogram()
        pixels = layer.width * layer.height
        if sum(histogram[:16]) < pixels * 0.01 or sum(histogram[240:]) < pixels * 0.001:
            continue
        borders = [alpha.crop((0, 0, layer.width, 1)),
                   alpha.crop((0, layer.height - 1, layer.width, layer.height)),
                   alpha.crop((0, 0, 1, layer.height)),
                   alpha.crop((layer.width - 1, 0, layer.width, layer.height))]
        border_visible = sum(sum(edge.histogram()[16:]) for edge in borders)
        if border_visible > 0.05 * (layer.width + layer.height) * 2:
            continue
        foreground = Image.alpha_composite(foreground, layer)
        selected += 1
    if not selected:
        raise InvalidAvatarImage("Geen vrijstaand poppetje gevonden in de modeluitvoer.")
    foreground = remove_alpha_noise(foreground)
    output = BytesIO()
    foreground.save(output, format="PNG")
    return validate_transparent_png(output.getvalue())


class QwenRuntime:
    def generate(self, source: bytes, reference: bytes) -> bytes:
        # Lazy imports keep the API/queue image and the idle service lightweight.
        require_capacity()
        try:
            import torch
            from diffusers import QwenImageEditPlusPipeline, QwenImageLayeredPipeline
        except ImportError as exc:
            raise InferenceUnavailable("The avatar-gpu dependencies are not installed") from exc
        if not torch.cuda.is_available():
            raise InferenceUnavailable("A supported CUDA runtime is required")
        # This runs inside the fresh model child. A limit in the HTTP parent
        # would not survive exec. It bounds PyTorch's allocator, not all driver
        # allocations or the shared host's total memory use.
        fraction = cuda_memory_fraction()
        try:
            torch.cuda.set_per_process_memory_fraction(fraction)
        except (RuntimeError, ValueError) as exc:
            raise InferenceUnavailable("The CUDA allocator memory budget could not be applied") from exc

        pipeline = None
        started = time.monotonic()
        event("avatar.model.loading", stage="edit")
        try:
            pipeline = QwenImageEditPlusPipeline.from_pretrained(
                EDIT_MODEL, revision=EDIT_REVISION, torch_dtype=torch.bfloat16,
                local_files_only=True, device_map="cuda", low_cpu_mem_usage=True,
            )
            pipeline.set_progress_bar_config(disable=True)
            event("avatar.model.loaded", stage="edit", duration_seconds=time.monotonic() - started)
            with torch.inference_mode():
                edited = pipeline(
                    image=[Image.open(BytesIO(source)).convert("RGB"),
                           Image.open(BytesIO(reference)).convert("RGB")],
                    prompt=AVATAR_PROMPT,
                    negative_prompt="checkerboard, text, scenery, multiple people, cropped figure",
                    true_cfg_scale=4.0, guidance_scale=1.0, num_inference_steps=40,
                    num_images_per_prompt=1,
                    generator=torch.Generator(device="cuda").manual_seed(777),
                    callback_on_step_end=_progress("edit", 40),
                    callback_on_step_end_tensor_inputs=[],
                ).images[0].copy()
        finally:
            # Release model 1 before loading model 2. CPU offload would not free
            # system RAM on Spark's shared-memory GB10 architecture.
            del pipeline
            gc.collect()
            torch.cuda.empty_cache()
            event("avatar.model.released", stage="edit", duration_seconds=time.monotonic() - started)

        require_capacity()
        pipeline = None
        event("avatar.model.loading", stage="layered")
        try:
            pipeline = QwenImageLayeredPipeline.from_pretrained(
                LAYERED_MODEL, revision=LAYERED_REVISION, torch_dtype=torch.bfloat16,
                local_files_only=True, device_map="cuda", low_cpu_mem_usage=True,
            )
            pipeline.set_progress_bar_config(disable=True)
            event("avatar.model.loaded", stage="layered", duration_seconds=time.monotonic() - started)
            with torch.inference_mode():
                layers = pipeline(
                    image=edited.convert("RGBA"),
                    generator=torch.Generator(device="cuda").manual_seed(777),
                    true_cfg_scale=4.0, negative_prompt=" ", num_inference_steps=50,
                    num_images_per_prompt=1, layers=4, resolution=640,
                    cfg_normalize=True, use_en_prompt=True,
                    callback_on_step_end=_progress("layered", 50),
                    callback_on_step_end_tensor_inputs=[],
                ).images[0]
                return foreground_from_layers(layers)
        finally:
            del pipeline
            gc.collect()
            torch.cuda.empty_cache()
            event("avatar.model.released", stage="layered", duration_seconds=time.monotonic() - started)


def _progress(stage: str, total: int):
    started = previous = time.monotonic()

    def report(_pipeline, step, _timestep, values):
        nonlocal previous
        now = time.monotonic()
        if step < 2 or (step + 1) % 5 == 0 or step + 1 == total:
            event("avatar.model.progress", stage=stage, step=step + 1, total=total,
                  duration_seconds=now - started)
        previous = now
        return values
    return report


def _decode_input(value) -> bytes:
    try:
        if not isinstance(value, str) or len(value) > MAX_UPLOAD_BYTES * 4 // 3 + 4:
            raise ValueError("Oversized image")
        return normalize_upload(base64.b64decode(value, validate=True), "image/png")
    except (ValueError, binascii.Error, InvalidAvatarImage) as exc:
        raise HTTPException(422, "Invalid source image") from exc


def generate_in_subprocess(source: bytes, reference: bytes) -> bytes:
    """A fresh process owns all CUDA state, including retained compiler buffers.

    PyTorch can retain model-dependent GPU buffers after del/GC/empty_cache.
    Exiting the isolated child releases these without restarting the HTTP app.
    """
    payload = json.dumps({"source_png": base64.b64encode(source).decode(),
                          "reference_png": base64.b64encode(reference).decode(),
                          "traceparent": current_traceparent()}).encode()
    process = subprocess.Popen(
        [sys.executable, "-m", "app.avatar_subprocess"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True,
        env={name: value for name, value in os.environ.items()
             if name not in {"AVATAR_SERVICE_TOKEN", "OPENAI_API_KEY", "DATABASE_URL"}},
    )
    try:
        result, _ = process.communicate(input=payload, timeout=3600)
    except BaseException:
        # Also clean up compiler subprocesses on timeout or request cancellation.
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        raise
    if process.returncode == 2:
        raise InvalidAvatarImage("The image model did not produce a transparent avatar")
    if process.returncode != 0:
        raise InferenceUnavailable("The isolated model process could not complete this job")
    return validate_transparent_png(result)


@app.get("/health/live")
def live():
    return {"status": "ok", "processing": generation_lock.locked()}


@app.post("/v1/avatar")
async def generate(request: Request):
    token = os.getenv("AVATAR_SERVICE_TOKEN", "")
    provided = request.headers.get("authorization", "")
    if not token or not hmac.compare_digest(provided, f"Bearer {token}"):
        raise HTTPException(401, "Invalid service credentials")
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(503, "The model is processing another avatar", headers={
            LOCAL_BUSY_HEADER: "busy", "Retry-After": str(LOCAL_BUSY_RETRY_SECONDS),
        })
    try:
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_OUTPUT_BYTES * 4 // 3 + 8192:
                raise HTTPException(413, "Image request too large")
        try:
            payload = json.loads(raw)
            source = _decode_input(payload["source_png"])
            reference = _decode_input(payload["reference_png"])
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            raise HTTPException(422, "Invalid image request") from exc
        started = time.monotonic()
        outcome, error_type = "success", "none"
        with operation_span("avatar.inference") as span:
            try:
                png = await run_in_threadpool(generate_in_subprocess, source, reference)
            except InferenceUnavailable as exc:
                outcome, error_type = "unavailable", "unavailable"
                raise HTTPException(503, "Avatar inference is not available on this host") from exc
            except InvalidAvatarImage as exc:
                outcome, error_type = "failure", "invalid_image"
                raise HTTPException(422, "The model did not produce a transparent avatar") from exc
            except Exception as exc:
                outcome, error_type = "failure", "unexpected"
                raise HTTPException(503, "The image model could not complete this job") from exc
            finally:
                span_result(span, outcome=outcome, error=error_type)
                event("avatar.inference.finished", outcome=outcome, error_type=error_type,
                      duration_seconds=time.monotonic() - started)
        return {"data": [{"b64_json": base64.b64encode(png).decode()}]}
    finally:
        generation_lock.release()


install_http(app, telemetry, accept_parent=True)
