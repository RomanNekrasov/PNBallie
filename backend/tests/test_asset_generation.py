import base64
import importlib.util
import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/generate_assets.py"
spec = importlib.util.spec_from_file_location("generate_assets", SCRIPT)
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


def icon():
    image = Image.new("RGBA", (1024, 1024))
    ImageDraw.Draw(image).ellipse((180, 180, 840, 840), fill="gold")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def config():
    return assets.configuration("azure", "gpt-image-2", "https://example.cognitiveservices.azure.com")


@pytest.mark.parametrize("endpoint", [
    "http://example.openai.azure.com", "https://example.openai.azure.com.evil.test",
    "https://user:password@example.openai.azure.com", "https://example.openai.azure.com/path",
    "https://example.openai.azure.com?key=value",
])
def test_azure_key_cannot_be_sent_to_unrelated_host(endpoint):
    with pytest.raises(ValueError, match="HTTPS-endpoint"):
        assets.configuration("azure", "gpt-image-2", endpoint)


def test_request_uses_existing_azure_contract_and_decodes_png(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    raw = icon()
    calls = []

    def handle(request):
        calls.append(request)
        assert str(request.url).endswith("/openai/v1/images/generations?api-version=preview")
        assert request.headers["api-key"] == "test-key"
        assert "authorization" not in request.headers
        assert json.loads(request.content)["n"] == 1
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(raw).decode()}]})

    result, _ = assets.generate_image(config(), {"n": 1}, transport=httpx.MockTransport(handle))
    assert result == raw
    assert len(calls) == 1
    assert assets.inspect_png(raw)["transparent_fraction"] > .5


@pytest.mark.parametrize("provider", ["azure", "openai"])
def test_http_failure_is_not_retried_or_leaked(monkeypatch, provider):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "private-key")
    monkeypatch.setenv("OPENAI_API_KEY", "private-key")
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(429, text="private provider details")

    selected = config() if provider == "azure" else assets.configuration("openai", "gpt-image-2", None)
    with pytest.raises(ValueError, match="HTTP 429") as error:
        assets.generate_image(selected, {}, transport=httpx.MockTransport(handle))
    assert "private" not in str(error.value)
    assert len(calls) == 1


def test_solid_or_empty_png_is_rejected():
    for color in ((255, 255, 255, 255), (0, 0, 0, 0)):
        output = BytesIO()
        Image.new("RGBA", (1024, 1024), color).save(output, format="PNG")
        with pytest.raises(ValueError, match="transparante"):
            assets.inspect_png(output.getvalue())


def test_resume_reuses_paid_result_but_refuses_changed_prompt_or_image(tmp_path, monkeypatch):
    catalog = assets.read_catalog(assets.CATALOG)
    job = assets.make_jobs(catalog, ["first_win"], ["pixel"], config(), "high")[0]
    calls = []

    def generate(*args):
        calls.append(args)
        return icon(), {}

    monkeypatch.setattr(assets, "generate_image", generate)
    assets.run_job(job, config(), tmp_path, False)
    assets.run_job(job, config(), tmp_path, True)
    assert len(calls) == 1
    catalog["styles"]["pixel"]["prompt"] += " Different style."
    changed = assets.make_jobs(catalog, ["first_win"], ["pixel"], config(), "high")[0]
    with pytest.raises(ValueError, match="bestaat"):
        assets.run_job(changed, config(), tmp_path, True)
    (tmp_path / job["file"]).write_bytes(b"damaged")
    with pytest.raises(ValueError, match="bestaat"):
        assets.run_job(job, config(), tmp_path, True)
    assert len(calls) == 1


def test_invalid_paid_result_is_preserved_and_never_automatically_retried(tmp_path, monkeypatch):
    catalog = assets.read_catalog(assets.CATALOG)
    job = assets.make_jobs(catalog, ["first_win"], ["pixel"], config(), "high")[0]
    monkeypatch.setattr(assets, "generate_image", lambda *args: (b"not an image", {}))
    with pytest.raises(ValueError):
        assets.run_job(job, config(), tmp_path, False)
    assert (tmp_path / job["file"]).read_bytes() == b"not an image"
    metadata = json.loads((tmp_path / job["file"]).with_suffix(".json").read_text())
    assert metadata["status"] == "failed"
    with pytest.raises(ValueError, match="onzekere poging"):
        assets.run_job(job, config(), tmp_path, True)


def test_web_export_removes_alpha_noise_without_removing_white_inside_the_icon():
    image = Image.new("RGBA", (1024, 1024))
    ImageDraw.Draw(image).rectangle((200, 200, 800, 800), fill="white")
    image.putpixel((0, 0), (255, 0, 0, 5))
    raw = BytesIO()
    image.save(raw, format="PNG")
    encoded, bounds = assets.web_icon(raw.getvalue())
    assert bounds == (200, 200, 801, 801)
    with Image.open(BytesIO(encoded)) as web:
        assert web.size == (256, 256)
        assert web.getpixel((128, 128)) == (255, 255, 255, 255)
        assert web.getpixel((0, 0))[3] == 0
    assert image.getpixel((0, 0)) == (255, 0, 0, 5)


def test_export_rejects_modified_source_before_writing_app_files(tmp_path, monkeypatch):
    catalog = assets.read_catalog(assets.CATALOG)
    job = assets.make_jobs(catalog, ["first_win"], ["game3d"], config(), "high")[0]
    source = tmp_path / "sources"
    source.mkdir()
    monkeypatch.setattr(assets, "generate_image", lambda *args: (icon(), {}))
    assets.run_job(job, config(), source, False)
    (source / job["file"]).write_bytes(b"modified")
    with pytest.raises(ValueError, match="geverifieerde"):
        assets.export_assets(catalog, source, tmp_path / "web", "game3d", ["first_win"])
    assert not (tmp_path / "web").exists()
