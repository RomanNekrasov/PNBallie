import base64
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from test_avatars import api as api
from test_avatars import enqueue, png

from app import avatar_readiness, avatar_service
from app.avatar_models import AvatarJob
from app.avatar_providers import AvatarProvider, AvatarSettings
from app.avatar_slot import gpu_slot
from app.avatar_worker import run_once
from app.routers import avatars


def test_capacity_probe_and_defer_require_auth_and_do_not_start_model(tmp_path, monkeypatch):
    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "test-token")
    monkeypatch.setenv("AVATAR_GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))

    def no_capacity():
        raise avatar_service.CapacityUnavailable("full")

    monkeypatch.setattr(avatar_service, "require_capacity", no_capacity)
    monkeypatch.setattr(avatar_service, "generate_in_subprocess", lambda *_: pytest.fail("No model child permitted"))
    client = TestClient(avatar_service.app)
    headers = {"Authorization": "Bearer test-token"}
    assert client.get("/v1/status").status_code == 401
    assert client.get("/v1/status", headers=headers).json() == {"state": "capacity"}
    encoded = base64.b64encode(png()).decode()
    response = client.post("/v1/avatar", headers=headers,
                           json={"style": "pixel-v1", "source_png": encoded})
    assert response.status_code == 503 and response.headers["X-PNBallie-Avatar-State"] == "capacity"
    with gpu_slot():
        assert client.get("/v1/status", headers=headers).json() == {"state": "busy"}
    monkeypatch.setattr(avatar_service, "require_capacity", lambda: None)
    assert client.get("/v1/status", headers=headers).json() == {"state": "ready"}


def test_known_capacity_shortage_rejects_upload_without_job_or_source(api, monkeypatch):
    client, database, _ = api

    async def capacity(_):
        return "capacity"

    monkeypatch.setattr(avatars, "local_status", capacity)
    assert client.get("/api/avatars/config").json()["local_status"] == "capacity"
    response = enqueue(client)
    assert response.status_code == 503 and "capaciteit" in response.json()["detail"]
    with Session(database) as session:
        assert session.exec(select(AvatarJob)).all() == []
    # No silent cloud switch, but an explicitly consented cloud request remains available.
    assert enqueue(client, params={"provider": "openai", "cloud_consent": True}).status_code == 202


def test_capacity_race_preserves_source_and_refunds_attempt(api):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    provider = AvatarProvider(transport=httpx.MockTransport(lambda _: httpx.Response(
        503, headers={"X-PNBallie-Avatar-State": "capacity", "Retry-After": "30"})))
    assert run_once(database, provider)
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        assert job.status == "queued" and job.attempts == 0 and job.source_png
        assert job.lease_token is None and job.leased_until is None
        assert "capaciteit" in job.error


@pytest.mark.anyio
async def test_readiness_is_bounded_private_and_opt_in(tmp_path, monkeypatch):
    settings = AvatarSettings("http://private/v1/avatar", "secret-test-token", "", "", tmp_path / "unused",
                              local_style="pixel-v1", check_capacity=True)
    original_client = httpx.AsyncClient
    seen = []

    def reply(request):
        seen.append(request)
        assert request.url == "http://private/v1/status"
        assert request.headers["Authorization"] == "Bearer secret-test-token"
        return httpx.Response(200, json={"state": "capacity"})

    monkeypatch.setattr(avatar_readiness.httpx, "AsyncClient",
                        lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(reply)))
    assert await avatar_readiness.local_status(replace(settings, check_capacity=False)) == "unknown"
    assert not seen
    assert await avatar_readiness.local_status(settings) == "capacity"
    assert len(seen) == 1 and seen[0].content == b""


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("status,payload", [(401, b"{}"), (302, b"{}"),
                         (200, b'{"state":[]}'), (200, b"not json"), (200, b"x" * 1025)])
async def test_invalid_readiness_cannot_enable_uploads(tmp_path, monkeypatch, status, payload):
    settings = AvatarSettings("http://private/v1/avatar", "test", "", "", tmp_path / "unused",
                              local_style="pixel-v1", check_capacity=True)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(avatar_readiness.httpx, "AsyncClient", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(lambda _: httpx.Response(status, content=payload))))
    assert await avatar_readiness.local_status(settings) == "unavailable"
