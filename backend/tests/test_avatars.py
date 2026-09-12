import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth import GroupContext, require_group, require_user
from app.avatar_images import (
    InvalidAvatarImage,
    normalize_upload,
    validate_transparent_png,
)
from app.avatar_models import AvatarJob, PlayerAvatar, avatar_url, utcnow
from app.avatar_providers import (
    LOCAL_BUSY_HEADER,
    AvatarProvider,
    AvatarProviderBusy,
    AvatarProviderError,
    AvatarSettings,
)
from app.avatar_service import foreground_from_layers
from app.avatar_worker import (
    claim_job,
    complete_job,
    defer_job,
    fail_job,
    renew_lease,
    run_once,
)
from app.database import get_session
from app.models import Group, Membership, Player, User, as_utc
from app.routers import avatars


def png(*, transparent=True, size=(64, 64)):
    image = Image.new("RGBA", size, (0, 0, 0, 0) if transparent else (10, 30, 100, 255))
    ImageDraw.Draw(image).rectangle((size[0] // 4, size[1] // 4,
                                    size[0] * 3 // 4, size[1] * 3 // 4), fill=(30, 200, 100, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("AVATAR_LOCAL_URL", "http://avatar-inference/v1/avatar")
    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "unit-test-service-token")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-openai-key")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "explicit-test-image-model")
    database = create_engine(f"sqlite:///{tmp_path / 'avatars.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(database)
    with Session(database) as session:
        session.add_all([Group(id=1, name="Pool one"), Group(id=2, name="Pool two")])
        session.add_all([User(id=i, email=f"test{i}@example.com", display_name=f"User {i}")
                         for i in range(1, 4)])
        session.commit()
        session.add_all([Membership(group_id=1, user_id=1), Membership(group_id=1, user_id=2),
                         Membership(group_id=2, user_id=3)])
        session.add_all([Player(id=1, name="Player 1", user_id=1, group_id=1),
                         Player(id=2, name="Player 2", user_id=2, group_id=1),
                         Player(id=3, name="Player 3", user_id=3, group_id=2)])
        session.commit()
        user = session.get(User, 1)
        session.expunge(user)
    application = FastAPI()
    application.include_router(avatars.router, prefix="/api")

    def get_test_session():
        with Session(database) as session:
            yield session

    application.dependency_overrides[get_session] = get_test_session
    application.dependency_overrides[require_user] = lambda: user
    application.dependency_overrides[require_group] = lambda: GroupContext(id=1, role="member", user=user)
    with TestClient(application) as client:
        yield client, database, application
    database.dispose()


def enqueue(client, **kwargs):
    return client.post("/api/avatars/me/jobs", content=png(),
                       headers={"Content-Type": "image/png"}, **kwargs)


def test_upload_is_queued_durable_and_does_not_call_provider(api):
    client, database, _ = api
    response = enqueue(client)
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "queued"
    assert job["created_at"].endswith("Z")
    assert "source_png" not in job and "cloud_consent" not in job
    assert client.get("/api/avatars/me/latest").json()["id"] == job["id"]
    assert enqueue(client).status_code == 409
    # A new engine represents a restarted worker, with no in-memory queue.
    restarted = create_engine(database.url)
    with Session(restarted) as session:
        persisted = session.get(AvatarJob, job["id"])
        assert persisted.source_png and persisted.active_player_id == 1
    restarted.dispose()


def test_upload_checks_format_cloud_consent_and_configuration(api, monkeypatch):
    client, _, _ = api
    assert enqueue(client, params={"provider": "openai"}).status_code == 422
    assert client.post("/api/avatars/me/jobs", content=b"not a photo",
                       headers={"Content-Type": "image/png"}).status_code == 422
    assert client.post("/api/avatars/me/jobs", content=png(),
                       headers={"Content-Type": "image/jpeg"}).status_code == 422
    assert client.post("/api/avatars/me/jobs", content=b"<svg />",
                       headers={"Content-Type": "image/svg+xml"}).status_code == 415
    monkeypatch.delenv("AVATAR_LOCAL_URL")
    assert enqueue(client).status_code == 503
    assert client.get("/api/avatars/config").json()["local_available"] is False
    assert enqueue(client, params={"provider": "openai", "cloud_consent": True}).status_code == 202


def test_upload_has_size_and_per_user_daily_limit(api):
    client, database, _ = api
    assert client.post("/api/avatars/me/jobs", content=b"x" * (8 * 1024 * 1024 + 1),
                       headers={"Content-Type": "image/png"}).status_code == 413
    for _ in range(5):
        response = enqueue(client)
        assert response.status_code == 202
        assert client.delete(f"/api/avatars/jobs/{response.json()['id']}").json()["status"] == "cancelled"
    assert enqueue(client).status_code == 429
    with Session(database) as session:
        assert all(job.source_png is None for job in session.exec(select(AvatarJob)).all())


def test_cannot_upload_for_unbound_or_inactive_profile(api):
    client, database, _ = api
    with Session(database) as session:
        player = session.get(Player, 1)
        player.user_id = None
        session.add(player)
        session.commit()
    assert enqueue(client).status_code == 409


class StubProvider:
    def generate(self, **_):
        return png()


def test_worker_publishes_transparent_png_and_deletes_source(api):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    assert run_once(database, StubProvider())
    assert not run_once(database, StubProvider())
    job = client.get(f"/api/avatars/jobs/{job_id}").json()
    assert job["status"] == "succeeded"
    assert job["avatar_url"] == f"/api/avatars/players/1.png?v={job_id}"
    media = client.get(job["avatar_url"])
    assert media.status_code == 200
    assert media.headers["cache-control"] == "private, no-store"
    assert validate_transparent_png(media.content)
    with Session(database) as session:
        assert session.get(AvatarJob, job_id).source_png is None
        assert session.get(AvatarJob, job_id).active_player_id is None
        assert avatar_url(session, 1) == job["avatar_url"]


def test_jobs_are_owner_only_and_images_require_real_group_membership(api):
    client, database, application = api
    job_id = enqueue(client).json()["id"]
    run_once(database, StubProvider())
    with Session(database) as session:
        peer, outsider = session.get(User, 2), session.get(User, 3)
        session.expunge_all()
    application.dependency_overrides[require_user] = lambda: peer
    application.dependency_overrides[require_group] = lambda: GroupContext(id=1, role="admin", user=peer)
    assert client.get("/api/avatars/players/1.png").status_code == 200
    assert client.get(f"/api/avatars/jobs/{job_id}").status_code == 404
    assert client.delete(f"/api/avatars/jobs/{job_id}").status_code == 404
    application.dependency_overrides[require_user] = lambda: outsider
    # Spoofing the active group header cannot make media visible.
    assert client.get("/api/avatars/players/1.png", headers={"X-Group-ID": "1"}).status_code == 404


@pytest.mark.parametrize("change", ["revoke", "rebind", "deactivate"])
def test_rebinding_or_membership_revocation_prevents_publication(api, change):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]

    class RevokingProvider:
        def generate(self, **_):
            with Session(database) as session:
                if change == "revoke":
                    session.delete(session.get(Membership, (1, 1)))
                else:
                    player = session.get(Player, 1)
                    if change == "rebind":
                        player.user_id = None
                    else:
                        player.is_active = False
                    session.add(player)
                session.commit()
            return png()

    run_once(database, RevokingProvider())
    with Session(database) as session:
        assert session.get(PlayerAvatar, 1) is None
        job = session.get(AvatarJob, job_id)
        assert job.status == "cancelled" and job.source_png is None


def test_cancelled_job_cannot_publish_late_result(api):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    claim = claim_job(database)
    response = client.delete(f"/api/avatars/jobs/{job_id}")
    assert response.json()["status"] == "cancelled"
    assert not complete_job(database, claim, png())
    with Session(database) as session:
        assert session.get(PlayerAvatar, 1) is None
        assert session.get(AvatarJob, job_id).source_png is None


def test_atomic_claim_allows_only_one_worker_and_fences_expired_worker(api):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = list(executor.map(lambda _: claim_job(database), range(2)))
    claims = [job for job in jobs if job]
    assert len(claims) == 1
    old_claim = claims[0]
    assert renew_lease(database, old_claim)
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        job.leased_until = utcnow() - timedelta(seconds=1)
        session.add(job)
        session.commit()
    new_claim = claim_job(database)
    assert new_claim.lease_token != old_claim.lease_token
    assert not complete_job(database, old_claim, png())
    assert not renew_lease(database, old_claim)
    assert complete_job(database, new_claim, png())


def test_retry_backoff_expiry_and_crash_limit_delete_source(api):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    claim = claim_job(database)
    fail_job(database, claim, "Temporary capacity problem", retryable=True)
    assert claim_job(database) is None
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        assert job.status == "queued" and job.source_png is not None
        job.created_at = utcnow() - timedelta(days=2)
        session.add(job)
        session.commit()
    assert claim_job(database) is None
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        assert job.status == "failed" and job.source_png is None
    second_id = enqueue(client).json()["id"]
    with Session(database) as session:
        job = session.get(AvatarJob, second_id)
        job.status = "processing"
        job.attempts = 3
        job.leased_until = utcnow() - timedelta(seconds=1)
        session.add(job)
        session.commit()
    assert claim_job(database) is None
    with Session(database) as session:
        assert session.get(AvatarJob, second_id).source_png is None


def test_shared_local_capacity_can_defer_repeatedly_then_complete_on_first_attempt(api, monkeypatch):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    now = [utcnow()]
    monkeypatch.setattr("app.avatar_worker.utcnow", lambda: now[0])

    class BusyProvider:
        calls = 0

        def generate(self, **_):
            self.calls += 1
            if self.calls <= 6:
                raise AvatarProviderBusy()
            return png()

    provider = BusyProvider()
    for _ in range(6):
        assert run_once(database, provider)
        with Session(database) as session:
            job = session.get(AvatarJob, job_id)
            assert job.status == "queued" and job.attempts == 0
            assert job.source_png and job.active_player_id == 1
            assert job.lease_token is None and job.leased_until is None
            assert as_utc(job.available_at) == now[0] + timedelta(seconds=30)
            assert session.get(PlayerAvatar, 1) is None
            available = as_utc(job.available_at)
        assert claim_job(database) is None
        now[0] = available
    assert run_once(database, provider)
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        assert job.status == "succeeded" and job.attempts == 1
        assert job.source_png is None and job.active_player_id is None
        assert validate_transparent_png(session.get(PlayerAvatar, 1).png)


def test_capacity_deferrals_preserve_prior_failures_and_real_failure_limit(api, monkeypatch):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    now = [utcnow()]
    monkeypatch.setattr("app.avatar_worker.utcnow", lambda: now[0])
    failures = iter([False, True, True, True, False, True, False])

    class MixedProvider:
        def generate(self, **_):
            if next(failures):
                raise AvatarProviderBusy()
            raise AvatarProviderError("Temporary inference failure", retryable=True)

    for attempts in (1, 1, 1, 1, 2, 2, 3):
        assert run_once(database, MixedProvider())
        with Session(database) as session:
            job = session.get(AvatarJob, job_id)
            assert job.attempts == attempts
            if attempts < 3:
                assert job.status == "queued" and job.source_png
                now[0] = as_utc(job.available_at)
            else:
                assert job.status == "failed" and job.source_png is None
                assert job.active_player_id is None
    assert not run_once(database, MixedProvider())


@pytest.mark.parametrize("expire_during_response", [False, True])
def test_capacity_waiting_does_not_extend_source_retention(api, monkeypatch, expire_during_response):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    now = [utcnow()]
    monkeypatch.setattr("app.avatar_worker.utcnow", lambda: now[0])
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        job.created_at = now[0] - timedelta(hours=24) + timedelta(seconds=1)
        session.add(job)
        session.commit()

    class BusyProvider:
        def generate(self, **_):
            if expire_during_response:
                now[0] += timedelta(seconds=2)
            raise AvatarProviderBusy()

    assert run_once(database, BusyProvider())
    if not expire_during_response:
        now[0] += timedelta(seconds=2)
        assert claim_job(database) is None
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        assert job.status == "failed" and job.source_png is None
        assert job.active_player_id is None and job.lease_token is None


def test_cancellation_wins_over_late_capacity_deferral(api):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]

    class CancellingProvider:
        def generate(self, **_):
            assert client.delete(f"/api/avatars/jobs/{job_id}").json()["status"] == "cancelled"
            raise AvatarProviderBusy()

    assert run_once(database, CancellingProvider())
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        assert job.status == "cancelled" and job.source_png is None
        assert job.active_player_id is None and job.lease_token is None
    assert claim_job(database) is None


@pytest.mark.parametrize("reclaimed", [False, True])
def test_expired_or_replaced_lease_cannot_refund_attempt_or_requeue_job(api, reclaimed):
    client, database, _ = api
    job_id = enqueue(client).json()["id"]
    old_claim = claim_job(database)
    with Session(database) as session:
        job = session.get(AvatarJob, job_id)
        job.leased_until = utcnow() - timedelta(seconds=1)
        session.add(job)
        session.commit()
    current_claim = claim_job(database) if reclaimed else old_claim
    with Session(database) as session:
        before = session.get(AvatarJob, job_id).model_dump()
    assert defer_job(database, old_claim, "Busy") == "fenced"
    with Session(database) as session:
        assert session.get(AvatarJob, job_id).model_dump() == before
    if reclaimed:
        assert defer_job(database, current_claim, "Busy") == "unavailable"
        with Session(database) as session:
            job = session.get(AvatarJob, job_id)
            assert job.attempts == 1 and job.status == "queued"


def test_invalid_model_output_is_failed_without_replacing_existing_avatar(api):
    client, database, _ = api
    enqueue(client)
    run_once(database, StubProvider())
    with Session(database) as session:
        first = session.get(PlayerAvatar, 1).version
    second_id = enqueue(client).json()["id"]

    class OpaqueProvider:
        def generate(self, **_):
            return png(transparent=False)

    run_once(database, OpaqueProvider())
    with Session(database) as session:
        assert session.get(PlayerAvatar, 1).version == first
        job = session.get(AvatarJob, second_id)
        assert job.status == "failed" and job.source_png is None


def test_image_sanitizing_and_real_alpha_check():
    normalized = normalize_upload(png(size=(1500, 600)), "image/png")
    image = Image.open(BytesIO(normalized))
    assert image.size == (1024, 410)
    assert "exif" not in image.info
    for raw in [png(transparent=False), b"not-png"]:
        with pytest.raises(InvalidAvatarImage):
            validate_transparent_png(raw)
    blank = BytesIO()
    Image.new("RGBA", (64, 64)).save(blank, format="PNG")
    with pytest.raises(InvalidAvatarImage):
        validate_transparent_png(blank.getvalue())
    with pytest.raises(InvalidAvatarImage):
        normalize_upload(png(size=(4100, 4100)), "image/png")


def test_upload_applies_exif_orientation_and_removes_metadata():
    photo = Image.new("RGB", (80, 40), (100, 20, 30))
    exif = Image.Exif()
    exif[274] = 6  # Rotate portrait into its displayed orientation.
    exif[270] = "Private camera description"
    source = BytesIO()
    photo.save(source, format="JPEG", exif=exif)
    normalized = Image.open(BytesIO(normalize_upload(source.getvalue(), "image/jpeg")))
    assert normalized.size == (40, 80)
    assert not normalized.getexif()
    assert "Private camera description" not in repr(normalized.info)


def test_layered_composes_all_transparent_foreground_and_discards_background():
    background = Image.new("RGBA", (64, 64), (0, 0, 200, 255))
    head = Image.new("RGBA", (64, 64))
    ImageDraw.Draw(head).rectangle((20, 5, 40, 25), fill=(200, 100, 80, 255))
    body = Image.new("RGBA", (64, 64))
    ImageDraw.Draw(body).rectangle((20, 25, 40, 58), fill=(20, 150, 80, 255))
    output = Image.open(BytesIO(foreground_from_layers([background, body, head])))
    assert output.getpixel((0, 0))[3] == 0
    assert output.getpixel((30, 10)) == (200, 100, 80, 255)
    assert output.getpixel((30, 40)) == (20, 150, 80, 255)
    with pytest.raises(InvalidAvatarImage):
        foreground_from_layers([background])


def test_layered_removes_background_alpha_noise_but_preserves_soft_edges():
    layer = Image.open(BytesIO(png())).copy()
    for x, alpha in enumerate([1, 15, 16, 64, 200], start=5):
        layer.putpixel((x, 5), (123, 45, 67, alpha))
    output = Image.open(BytesIO(foreground_from_layers([layer])))
    for x in [5, 6]:
        assert output.getpixel((x, 5)) == (123, 45, 67, 0)
    for x, alpha in [(7, 16), (8, 64), (9, 200)]:
        assert output.getpixel((x, 5)) == (123, 45, 67, alpha)


def test_provider_never_falls_back_or_sends_cloud_without_consent(tmp_path):
    reference = tmp_path / "reference.png"
    reference.write_bytes(png())
    settings = AvatarSettings("http://private/v1/avatar", "test-token", "cloud-key",
                              "explicit-model", reference)
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(503)

    provider = AvatarProvider(settings, transport=httpx.MockTransport(handle))
    with pytest.raises(AvatarProviderError):
        provider.generate(source_png=png(), provider="openai", cloud_consent=False, job_id="j1")
    assert not calls
    with pytest.raises(AvatarProviderError) as error:
        provider.generate(source_png=png(), provider="local", cloud_consent=True, job_id="j1")
    assert error.value.retryable
    assert len(calls) == 1 and calls[0].url.host == "private"


@pytest.mark.parametrize("retry_after,expected_delay", [
    ("45", 45), ("1", 30), ("999", 300), ("9999999999999999999999", 30),
    ("-1", 30), ("Wed, 21 Oct 2030 07:28:00 GMT", 30), ("", 30),
])
def test_local_provider_recognizes_explicit_busy_signal_with_bounded_delay(tmp_path, retry_after, expected_delay):
    reference = tmp_path / "reference.png"
    reference.write_bytes(png())
    settings = AvatarSettings("http://private/v1/avatar", "test-token", "", "", reference)

    class UnreadBody(httpx.SyncByteStream):
        def __iter__(self):
            raise AssertionError("Busy responses must not consume an arbitrary response body")

    transport = httpx.MockTransport(lambda _: httpx.Response(
        503, headers={LOCAL_BUSY_HEADER: "busy", "Retry-After": retry_after}, stream=UnreadBody(),
    ))
    provider = AvatarProvider(settings, transport=transport)
    with pytest.raises(AvatarProviderBusy) as error:
        provider.generate(source_png=png(), provider="local", cloud_consent=False, job_id="busy-test")
    assert error.value.retry_after == expected_delay


@pytest.mark.parametrize("provider_name,status,state", [
    ("local", 503, ""), ("local", 503, "unavailable"), ("local", 502, "busy"),
    ("local", 429, "busy"), ("openai", 503, "busy"),
])
def test_generic_errors_and_cloud_responses_are_never_capacity_deferrals(tmp_path, provider_name, status, state):
    reference = tmp_path / "reference.png"
    reference.write_bytes(png())
    settings = AvatarSettings("http://private/v1/avatar", "test-token", "cloud-key", "explicit-model", reference)
    provider = AvatarProvider(settings, transport=httpx.MockTransport(lambda _: httpx.Response(
        status, headers={LOCAL_BUSY_HEADER: state, "Retry-After": "30"}, json={"detail": "busy"},
    )))
    with pytest.raises(AvatarProviderError) as error:
        provider.generate(source_png=png(), provider=provider_name, cloud_consent=True, job_id="error-test")
    assert type(error.value) is AvatarProviderError
    assert error.value.retryable


def test_openai_edits_contract_requests_transparent_png_with_two_images(tmp_path):
    reference = tmp_path / "reference.png"
    reference.write_bytes(png())
    settings = AvatarSettings("", "", "test-key", "explicit-model", reference)

    def handle(request):
        assert str(request.url) == "https://api.openai.com/v1/images/edits"
        body = request.read()
        assert body.count(b'name="image[]"') == 2
        assert b"transparent" in body and b"explicit-model" in body
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png()).decode()}]})

    provider = AvatarProvider(settings, transport=httpx.MockTransport(handle))
    assert validate_transparent_png(provider.generate(source_png=png(), provider="openai",
                                                     cloud_consent=True, job_id="test"))


def test_service_requires_token_and_does_not_load_model_if_capacity_is_missing(monkeypatch):
    from app import avatar_service

    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "service-token")
    monkeypatch.setattr(avatar_service, "generate_in_subprocess", lambda *_: (_ for _ in ()).throw(
        avatar_service.InferenceUnavailable("Insufficient memory")))
    client = TestClient(avatar_service.app)
    payload = {"source_png": base64.b64encode(png()).decode(),
               "reference_png": base64.b64encode(png()).decode()}
    assert client.post("/v1/avatar", json=payload).status_code == 401
    response = client.post("/v1/avatar", json=payload,
                           headers={"Authorization": "Bearer service-token"})
    assert response.status_code == 503
    assert LOCAL_BUSY_HEADER not in response.headers
    assert not avatar_service.generation_lock.locked()


def test_service_signals_busy_only_after_auth_and_without_starting_another_generation(monkeypatch):
    from app import avatar_service

    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "service-token")

    def unexpected_generation(*_):
        raise AssertionError("An occupied slot must not start another model child")

    monkeypatch.setattr(avatar_service, "generate_in_subprocess", unexpected_generation)
    client = TestClient(avatar_service.app)
    with avatar_service.generation_lock:
        unauthorized = client.post("/v1/avatar", json={})
        assert unauthorized.status_code == 401 and LOCAL_BUSY_HEADER not in unauthorized.headers
        response = client.post("/v1/avatar", json={}, headers={"Authorization": "Bearer service-token"})
        assert response.status_code == 503
        assert response.headers[LOCAL_BUSY_HEADER] == "busy" and response.headers["Retry-After"] == "30"
        assert avatar_service.generation_lock.locked()
    invalid = client.post("/v1/avatar", json={}, headers={"Authorization": "Bearer service-token"})
    assert invalid.status_code == 422 and LOCAL_BUSY_HEADER not in invalid.headers


def test_service_returns_real_png_protocol_without_gpu_or_cloud(monkeypatch):
    from app import avatar_service

    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "service-token")
    monkeypatch.setattr(avatar_service, "generate_in_subprocess", lambda source, reference: png())
    client = TestClient(avatar_service.app)
    encoded = base64.b64encode(png()).decode()
    response = client.post("/v1/avatar", json={"source_png": encoded, "reference_png": encoded},
                           headers={"Authorization": "Bearer service-token"})
    assert response.status_code == 200
    assert validate_transparent_png(base64.b64decode(response.json()["data"][0]["b64_json"]))


@pytest.mark.parametrize("configured_fraction,expected_fraction", [(None, 0.70), ("0.55", 0.55), ("1", 1.0)])
def test_gpu_runtime_applies_budget_before_loading_and_releases_each_model(monkeypatch, configured_fraction, expected_fraction):
    import sys
    import weakref
    from contextlib import nullcontext
    from types import SimpleNamespace

    from app import avatar_service

    if configured_fraction is None:
        monkeypatch.delenv("AVATAR_CUDA_MEMORY_FRACTION", raising=False)
    else:
        monkeypatch.setenv("AVATAR_CUDA_MEMORY_FRACTION", configured_fraction)
    events = []
    active = []

    class FakePipeline:
        def __init__(self, name):
            self.name = name

        @classmethod
        def from_pretrained(cls, name, **kwargs):
            assert events[:2] == ["cuda_available", ("budget", expected_fraction)], "weights loaded before the CUDA budget"
            assert not any(ref() for ref in active), "previous model is still retained"
            assert kwargs["device_map"] == "cuda" and kwargs["low_cpu_mem_usage"] is True
            assert kwargs["local_files_only"] is True and len(kwargs["revision"]) == 40
            result = cls(name)
            active.append(weakref.ref(result))
            events.append("load")
            return result

        def set_progress_bar_config(self, **_):
            pass

        def __call__(self, **kwargs):
            if "layers" in kwargs:
                assert kwargs["num_inference_steps"] == 50 and kwargs["resolution"] == 640
            else:
                assert kwargs["num_inference_steps"] == 40
            image = Image.open(BytesIO(png())).copy()
            return SimpleNamespace(images=[[image]] if "layers" in kwargs else [image])

    fake_torch = SimpleNamespace(
        bfloat16="bf16", inference_mode=nullcontext,
        Generator=lambda **_: SimpleNamespace(manual_seed=lambda _: 777),
        cuda=SimpleNamespace(
            is_available=lambda: events.append("cuda_available") or True,
            set_per_process_memory_fraction=lambda fraction: events.append(("budget", fraction)),
            empty_cache=lambda: events.append("release"),
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(
        QwenImageEditPlusPipeline=FakePipeline, QwenImageLayeredPipeline=FakePipeline))
    monkeypatch.setattr(avatar_service, "require_capacity", lambda: None)
    assert validate_transparent_png(avatar_service.QwenRuntime().generate(png(), png()))
    assert events == ["cuda_available", ("budget", expected_fraction), "load", "release", "load", "release"]
    assert not any(ref() for ref in active)


@pytest.mark.parametrize("configured_fraction", ["", "invalid", "nan", "inf", "-inf", "0", "-0.1", "1.01", "1e999"])
def test_invalid_cuda_budget_stops_before_allocator_or_model_load(monkeypatch, configured_fraction):
    import sys
    from types import SimpleNamespace

    from app import avatar_service

    monkeypatch.setenv("AVATAR_CUDA_MEMORY_FRACTION", configured_fraction)
    monkeypatch.setattr(avatar_service, "require_capacity", lambda: None)
    calls = []
    pipeline = SimpleNamespace(from_pretrained=lambda *_args, **_kwargs: calls.append("load"))
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(
        QwenImageEditPlusPipeline=pipeline, QwenImageLayeredPipeline=pipeline))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(
        is_available=lambda: True,
        set_per_process_memory_fraction=lambda _fraction: calls.append("budget"),
    )))
    with pytest.raises(avatar_service.InferenceUnavailable, match="AVATAR_CUDA_MEMORY_FRACTION"):
        avatar_service.QwenRuntime().generate(png(), png())
    assert calls == []


def test_failed_cuda_budget_application_never_loads_unbounded_models(monkeypatch):
    import sys
    from types import SimpleNamespace

    from app import avatar_service

    monkeypatch.delenv("AVATAR_CUDA_MEMORY_FRACTION", raising=False)
    monkeypatch.setattr(avatar_service, "require_capacity", lambda: None)
    calls = []

    def failed_budget(_fraction):
        calls.append("budget")
        raise RuntimeError("Synthetic allocator configuration failure")

    pipeline = SimpleNamespace(from_pretrained=lambda *_args, **_kwargs: calls.append("load"))
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(
        QwenImageEditPlusPipeline=pipeline, QwenImageLayeredPipeline=pipeline))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(
        is_available=lambda: True, set_per_process_memory_fraction=failed_budget,
    )))
    with pytest.raises(avatar_service.InferenceUnavailable, match="budget could not be applied"):
        avatar_service.QwenRuntime().generate(png(), png())
    assert calls == ["budget"]


def test_isolated_model_protocol_waits_for_process_exit(monkeypatch):
    import subprocess
    import sys

    from app import avatar_service

    original_popen = subprocess.Popen
    processes = []
    encoded = base64.b64encode(png()).decode()
    program = (
        "import sys,json,base64; d=json.loads(sys.stdin.buffer.read());"
        "assert base64.b64decode(d['source_png']).startswith(b'\\x89PNG');"
        f"sys.stdout.buffer.write(base64.b64decode('{encoded}'))"
    )

    def launch(_command, **kwargs):
        process = original_popen([sys.executable, "-c", program], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(avatar_service.subprocess, "Popen", launch)
    assert validate_transparent_png(avatar_service.generate_in_subprocess(png(), png()))
    assert len(processes) == 1 and processes[0].poll() == 0


@pytest.mark.parametrize("code,error", [(2, InvalidAvatarImage), (3, RuntimeError)])
def test_isolated_model_failure_is_not_a_successful_avatar(monkeypatch, code, error):
    import subprocess
    import sys

    from app import avatar_service

    original_popen = subprocess.Popen

    def launch(_command, **kwargs):
        return original_popen([sys.executable, "-c", f"import sys; sys.stdin.buffer.read(); sys.exit({code})"], **kwargs)

    monkeypatch.setattr(avatar_service.subprocess, "Popen", launch)
    with pytest.raises(error):
        avatar_service.generate_in_subprocess(png(), png())


def test_isolated_model_timeout_terminates_its_process_group(monkeypatch):
    import signal
    import subprocess
    from types import SimpleNamespace

    from app import avatar_service

    events = []

    def communicate(**_):
        raise subprocess.TimeoutExpired("model", 3600)

    process = SimpleNamespace(pid=1234, communicate=communicate,
                              wait=lambda **_: events.append("reaped"))
    monkeypatch.setattr(avatar_service.subprocess, "Popen", lambda *_, **__: process)
    monkeypatch.setattr(avatar_service.os, "killpg", lambda pid, sig: events.append((pid, sig)))
    with pytest.raises(subprocess.TimeoutExpired):
        avatar_service.generate_in_subprocess(png(), png())
    assert events == [(1234, signal.SIGTERM), "reaped"]
