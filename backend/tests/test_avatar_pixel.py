import base64
import json
import sys
from contextlib import nullcontext
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import avatar_service
from app.avatar_images import InvalidAvatarImage, validate_transparent_png
from app.avatar_pixel import (
    PIXEL_PROMPT,
    PIXEL_STYLE,
    compose_pixel_avatar,
    extract_pixel_head,
    pixel_template,
    place_pixel_head,
)
from app.avatar_providers import AvatarProvider, AvatarProviderError, AvatarSettings


def portrait():
    image = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((65, 20, 191, 220), fill=(175, 115, 80))
    draw.rectangle((101, 185, 155, 255), fill=(175, 115, 80))
    draw.rectangle((90, 90, 100, 100), fill="white")
    return image


def png(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_transparency_preserves_enclosed_white_and_original_body_pixels():
    head = extract_pixel_head(portrait())
    assert head.getpixel((95 - 65, 95 - 20)) == (255, 255, 255, 255)
    body = pixel_template()
    result = place_pixel_head(head, body)
    body_region = result.crop((0, result.height - body.height, body.width, result.height)).tobytes()
    original = body.tobytes()
    visible = [i for i in range(0, len(original), 4) if original[i + 3]]
    assert len(visible) == 532097
    assert all(original[i:i + 4] == body_region[i:i + 4] for i in visible)
    output = compose_pixel_avatar(portrait(), body)
    validated = Image.open(BytesIO(validate_transparent_png(output)))
    assert validated.size == (640, 640) and validated.mode == "RGBA"
    assert not validated.getexif()
    assert all(validated.getpixel(point)[3] == 0 for point in [(0, 0), (639, 639), (320, 0)])


@pytest.mark.parametrize("image", [Image.new("RGB", (256, 256), "white"),
                                   Image.new("RGB", (256, 256), "black"),
                                   Image.new("RGB", (2000, 64), "white")])
def test_invalid_model_outputs_do_not_turn_into_headless_or_opaque_avatars(image):
    with pytest.raises(InvalidAvatarImage):
        compose_pixel_avatar(image, pixel_template())


def test_pixel_runtime_uses_one_model_and_one_portrait_then_releases_gpu(monkeypatch):
    events = []

    class Pipeline:
        @classmethod
        def from_pretrained(cls, name, **kwargs):
            assert events == ["budget"]
            assert name == avatar_service.EDIT_MODEL
            events.append("load")
            return cls()

        def set_progress_bar_config(self, **_):
            pass

        def __call__(self, **kwargs):
            assert len(kwargs["image"]) == 1
            assert kwargs["image"][0].getpixel((0, 0)) == (255, 255, 255)
            assert kwargs["prompt"] == PIXEL_PROMPT
            assert kwargs["width"] == kwargs["height"] == 1024
            assert kwargs["num_inference_steps"] == 40
            return SimpleNamespace(images=[portrait()])

    class NoLayered:
        @classmethod
        def from_pretrained(cls, *_, **__):
            raise AssertionError("Pixel avatars must not load the Layered model")

    fake_torch = SimpleNamespace(
        bfloat16="bf16", inference_mode=nullcontext,
        Generator=lambda **_: SimpleNamespace(manual_seed=lambda _: 777),
        cuda=SimpleNamespace(is_available=lambda: True,
                             set_per_process_memory_fraction=lambda _: events.append("budget"),
                             empty_cache=lambda: events.append("release")),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(
        QwenImageEditPlusPipeline=Pipeline, QwenImageLayeredPipeline=NoLayered))
    monkeypatch.setattr(avatar_service, "require_capacity", lambda: None)
    source = png(Image.new("RGBA", (256, 256)))
    assert validate_transparent_png(avatar_service.QwenRuntime().generate(source, b"", style=PIXEL_STYLE))
    assert events == ["budget", "load", "release"]


def test_provider_and_service_negotiate_pixel_style_without_transmitting_body(tmp_path, monkeypatch):
    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "pixel-test-token")
    monkeypatch.setenv("AVATAR_GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    calls = []

    def generate(source, reference, *, style):
        calls.append(style)
        assert reference == b""
        assert Image.open(BytesIO(source)).size == (256, 256)
        return compose_pixel_avatar(portrait(), pixel_template())

    monkeypatch.setattr(avatar_service, "require_capacity", lambda: None)
    monkeypatch.setattr(avatar_service, "generate_in_subprocess", generate)
    service = TestClient(avatar_service.app)
    settings = AvatarSettings("http://private/v1/avatar", "pixel-test-token", "", "",
                              tmp_path / "nonexistent-legacy-template.png", local_style=PIXEL_STYLE)

    def transport(request):
        payload = json.loads(request.read())
        assert set(payload) == {"source_png", "style"}
        response = service.post("/v1/avatar", json=payload,
                                headers={"Authorization": request.headers["Authorization"]})
        return httpx.Response(response.status_code, json=response.json())

    provider = AvatarProvider(settings, transport=httpx.MockTransport(transport))
    assert validate_transparent_png(provider.generate(source_png=png(portrait()), provider="local",
                                                    cloud_consent=False, job_id="test"))
    assert calls == [PIXEL_STYLE]
    bad = service.post("/v1/avatar", json={"style": ["unexpected"]},
                       headers={"Authorization": "Bearer pixel-test-token"})
    assert bad.status_code == 422 and len(calls) == 1
    assert not replace(settings, local_style="unknown").local_available


def test_old_service_cannot_silently_return_legacy_style(tmp_path):
    settings = AvatarSettings("http://private/v1/avatar", "test", "", "", tmp_path / "absent",
                              local_style=PIXEL_STYLE)
    response = {"data": [{"b64_json": base64.b64encode(png(portrait())).decode()}]}
    provider = AvatarProvider(settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)))
    with pytest.raises(AvatarProviderError, match="avatarstijl") as error:
        provider.generate(source_png=png(portrait()), provider="local", cloud_consent=False, job_id="test")
    assert not error.value.retryable
