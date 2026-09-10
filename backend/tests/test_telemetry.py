import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO, StringIO
from threading import Thread

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from PIL import Image, ImageDraw
from sqlmodel import Session, SQLModel, create_engine

from app import telemetry
from app.auth import GroupContext, require_group, require_user
from app.avatar_models import AvatarJob
from app.avatar_providers import AvatarProvider, AvatarProviderError, AvatarSettings
from app.database import get_session
from app.models import Group, Membership, Player, User
from app.routers import avatars


@pytest.fixture
def runtime_factory(monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "1")
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "preview")
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    # Restore pytest's logging handlers when these independently configured
    # service runtimes close, rather than retaining a closed StringIO handler.
    monkeypatch.setattr(logging.getLogger(), "handlers", list(logging.getLogger().handlers))
    instances = []

    def factory(service=telemetry.API_SERVICE, database=None):
        spans, logs, stream = InMemorySpanExporter(), InMemoryLogRecordExporter(), StringIO()
        monkeypatch.setattr(telemetry, "OTLPSpanExporter", lambda **_: spans)
        monkeypatch.setattr(telemetry, "OTLPLogExporter", lambda **_: logs)
        runtime = telemetry.Runtime(service, database)
        runtime.configure(console_stream=stream)
        instances.append(runtime)
        return runtime, spans, logs, stream
    yield factory
    for runtime in instances:
        runtime.close()


def flush(runtime):
    assert runtime.tracer_provider.force_flush(timeout_millis=2000)
    assert runtime.log_provider.force_flush(timeout_millis=2000)


def raw_png():
    image = Image.new("RGBA", (64, 64))
    ImageDraw.Draw(image).rectangle((20, 10, 42, 54), fill=(20, 150, 70, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_http_telemetry_contains_templates_and_never_sensitive_request_or_exception_text(runtime_factory):
    runtime, spans, logs, console = runtime_factory()
    application = FastAPI()

    @application.post("/api/test-users/{user_id}")
    async def success(user_id: str, request: Request):
        await request.body()
        return {"ok": True}

    @application.get("/api/test-error/{job_id}")
    def failure(job_id: str):
        try:
            raise RuntimeError("exception-photo-body-token=secret-exception")
        except RuntimeError:
            logging.getLogger("httpx").exception("POST https://secret-provider/path?key=secret-library")
            raise

    telemetry.install_http(application, runtime)
    with TestClient(application, raise_server_exceptions=False) as client:
        assert client.post("/api/test-users/private-person?email=secret-email@example.org", content=b"secret-photo-body", headers={"Cookie": "session=secret-cookie", "Authorization": "Bearer secret-bearer", "baggage": "email=secret-baggage"}).status_code == 200
        assert client.get("/api/test-error/secret-job-id").status_code == 500
        for suffix in range(5):
            assert client.get(f"/private-unknown-{suffix}").status_code == 404
        metrics = client.get("/metrics").text
    flush(runtime)
    finished = spans.get_finished_spans()
    assert [span.name for span in finished[:2]] == ["POST /api/test-users/{user_id}", "GET /api/test-error/{job_id}"]
    assert finished[1].status.status_code.name == "ERROR"
    assert all(not span.events for span in finished)  # No automatic exceptions/stacks.
    assert all(span.resource.attributes["deployment.environment.name"] == "preview" for span in finished)
    records = logs.get_finished_logs()
    assert len(records) == 7  # Only explicitly safe request events go to OTLP.
    record = records[0].log_record
    assert record.trace_id == finished[0].context.trace_id
    assert record.span_id == finished[0].context.span_id
    assert record.body["trace_id"] == f"{record.trace_id:032x}"
    assert record.body["route"] == "/api/test-users/{user_id}"
    combined = console.getvalue() + metrics + repr([(span.name, span.attributes, span.events) for span in finished]) + repr([r.log_record.body for r in records])
    for secret in ("private-person", "secret-email", "secret-photo", "secret-cookie", "secret-bearer", "secret-baggage", "secret-exception", "secret-provider", "secret-library", "secret-job-id", "private-unknown-"):
        assert secret not in combined
    assert 'route="/api/test-users/{user_id}"' in metrics
    assert 'route="unmatched"' in metrics
    assert 'status_code="500"' in metrics
    assert logging.getLogger("uvicorn.access").disabled
    assert all(json.loads(line)["event"] in telemetry.EVENTS for line in console.getvalue().splitlines())


def test_metrics_disabled_by_default_and_environment_override_is_allowlisted(monkeypatch):
    monkeypatch.delenv("METRICS_ENABLED", raising=False)
    application = FastAPI()
    runtime = telemetry.Runtime(telemetry.API_SERVICE)
    telemetry.install_http(application, runtime)
    assert TestClient(application).get("/metrics").status_code == 404
    monkeypatch.delenv("DEPLOYMENT_ENVIRONMENT", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "account.email=secret@example.org,deployment.environment.name=preview")
    assert telemetry.environment() == "preview"
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "staging")
    assert telemetry.environment() == "staging"
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "secret-person")
    assert telemetry.environment() == "other"


def test_unconfigured_or_failed_telemetry_does_not_change_http_or_raise(runtime_factory, monkeypatch):
    runtime, _, _, console = runtime_factory()

    class BrokenTracer:
        def start_as_current_span(self, *_, **__):
            raise RuntimeError("secret exporter credentials")
    runtime.tracer = BrokenTracer()
    runtime.log_writer = type("BrokenLogWriter", (), {"emit": lambda *_: (_ for _ in ()).throw(RuntimeError("secret provider response"))})()
    application = FastAPI()

    @application.get("/api/test-fail-open")
    def endpoint():
        return {"ok": True}
    telemetry.install_http(application, runtime)
    assert TestClient(application).get("/api/test-fail-open").json() == {"ok": True}
    assert "secret" not in console.getvalue()
    runtime.close()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://user:secret@invalid.test/?token=secret")
    runtime.configure(console_stream=console)
    assert runtime.log_writer is None
    assert "secret" not in console.getvalue()


def test_durable_avatar_trace_links_api_worker_provider_and_inference(runtime_factory, monkeypatch, tmp_path):
    from app import avatar_service, avatar_worker

    monkeypatch.setenv("AVATAR_LOCAL_URL", "http://inference/v1/avatar")
    monkeypatch.setenv("AVATAR_SERVICE_TOKEN", "secret-service-token")
    database = create_engine(f"sqlite:///{tmp_path / 'trace-queue.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(database)
    with Session(database) as session:
        session.add_all([Group(id=1, name="secret-group-name"), User(id=1, email="secret@example.org", display_name="secret-display-name")])
        session.commit()
        session.add_all([Membership(group_id=1, user_id=1), Player(id=1, group_id=1, user_id=1, name="secret-player-name")])
        session.commit()
        user = session.get(User, 1)
        session.expunge(user)
    api_runtime, api_spans, api_logs, _ = runtime_factory(telemetry.API_SERVICE, database)
    application = FastAPI()
    application.include_router(avatars.router, prefix="/api")
    telemetry.install_http(application, api_runtime)

    def session_override():
        with Session(database) as session:
            yield session
    application.dependency_overrides[get_session] = session_override
    application.dependency_overrides[require_user] = lambda: user
    application.dependency_overrides[require_group] = lambda: GroupContext(id=1, role="member", user=user)
    client = TestClient(application)
    upload = client.post("/api/avatars/me/jobs", content=raw_png(), headers={"Content-Type": "image/png"})
    assert upload.status_code == 202
    job_id = upload.json()["id"]
    with Session(database) as session:
        stored_parent = session.get(AvatarJob, job_id).traceparent
        assert telemetry.TRACEPARENT.fullmatch(stored_parent)
    # A separate engine/session demonstrates that context travels through the
    # persisted queue record, not through the API thread's local context.
    restarted = create_engine(database.url, connect_args={"check_same_thread": False})
    worker_runtime, worker_spans, worker_logs, _ = runtime_factory(telemetry.WORKER_SERVICE, restarted)
    monkeypatch.setattr(avatar_worker, "telemetry", worker_runtime)
    inference_runtime, inference_spans, inference_logs, _ = runtime_factory(telemetry.INFERENCE_SERVICE)
    inference_app = FastAPI()
    inference_app.post("/v1/avatar")(avatar_service.generate)
    telemetry.install_http(inference_app, inference_runtime, accept_parent=True)
    monkeypatch.setattr(avatar_service, "generate_in_subprocess", lambda *_: raw_png())
    inference_client = TestClient(inference_app)
    observed = []

    def handle(request):
        observed.append(dict(request.headers))
        response = inference_client.post("/v1/avatar", content=request.content, headers=dict(request.headers))
        return httpx.Response(response.status_code, content=response.content)
    reference = tmp_path / "body.png"
    reference.write_bytes(raw_png())
    provider = AvatarProvider(AvatarSettings("http://inference/v1/avatar", "secret-service-token", "", "", reference), transport=httpx.MockTransport(handle))
    assert avatar_worker.run_once(restarted, provider)
    assert observed[0]["traceparent"].split("-")[1] == stored_parent.split("-")[1]
    assert "baggage" not in observed[0] and "tracestate" not in observed[0]
    for runtime in (api_runtime, worker_runtime, inference_runtime):
        flush(runtime)
    spans = api_spans.get_finished_spans() + worker_spans.get_finished_spans() + inference_spans.get_finished_spans()
    assert len({span.context.trace_id for span in spans}) == 1
    process = next(span for span in spans if span.name == "avatar.process")
    assert process.parent.span_id == int(stored_parent.split("-")[2], 16)
    names = {span.name for span in spans}
    assert {"POST /api/avatars/me/jobs", "avatar.process", "avatar.provider", "POST /v1/avatar", "avatar.inference"} <= names
    services = {span.resource.attributes["service.name"] for span in spans}
    assert services == telemetry.SERVICES
    logs = api_logs.get_finished_logs() + worker_logs.get_finished_logs() + inference_logs.get_finished_logs()
    assert all(log.log_record.trace_id == process.context.trace_id for log in logs)
    combined = repr([(span.name, span.attributes) for span in spans]) + repr([log.log_record.body for log in logs])
    assert "secret" not in combined and job_id not in combined
    with Session(restarted) as session:
        assert session.get(AvatarJob, job_id).status == "succeeded"
    metrics = client.get("/metrics").text
    assert 'pnballie_avatar_queue_jobs{provider="local",service="pnballie-api",state="queued"} 0.0' in metrics
    assert 'pnballie_avatar_provider_requests_total{outcome="success",provider="local",service="pnballie-avatar-worker"}' in metrics
    client.close()
    inference_client.close()
    database.dispose()
    restarted.dispose()


def test_cloud_provider_receives_no_trace_context_and_error_body_is_not_recorded(runtime_factory, tmp_path):
    runtime, spans, logs, console = runtime_factory(telemetry.WORKER_SERVICE)
    reference = tmp_path / "reference.png"
    reference.write_bytes(raw_png())
    observed = []

    def handle(request):
        observed.append(dict(request.headers))
        return httpx.Response(503, text="secret-photo-and-provider-response")
    provider = AvatarProvider(AvatarSettings("", "", "secret-cloud-key", "explicit-model", reference), transport=httpx.MockTransport(handle))
    with runtime.span("avatar.process", root=True):
        with pytest.raises(AvatarProviderError):
            provider.generate(source_png=raw_png(), provider="openai", cloud_consent=True, job_id="secret-job")
    flush(runtime)
    assert "traceparent" not in observed[0] and "baggage" not in observed[0]
    exported = repr([(span.name, span.attributes, span.events) for span in spans.get_finished_spans()]) + repr([record.log_record.body for record in logs.get_finished_logs()]) + console.getvalue()
    assert "secret" not in exported
    provider_span = next(span for span in spans.get_finished_spans() if span.name == "avatar.provider")
    assert provider_span.status.status_code.name == "ERROR"
    assert not provider_span.events


def test_otlp_http_exports_actual_protobuf_traces_and_logs_with_correlation(monkeypatch):
    received = {}

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self):
            received.setdefault(self.path, []).append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "1")
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "preview")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.setattr(logging.getLogger(), "handlers", list(logging.getLogger().handlers))
    runtime = telemetry.Runtime(telemetry.API_SERVICE)
    try:
        runtime.configure(console_stream=StringIO())
        with runtime.span("safe.export.test", root=True):
            telemetry.event("http.request", method="GET", route="unmatched", status_code=200)
        flush(runtime)
        trace_request = ExportTraceServiceRequest.FromString(received["/v1/traces"][0])
        log_request = ExportLogsServiceRequest.FromString(received["/v1/logs"][0])
        span = trace_request.resource_spans[0].scope_spans[0].spans[0]
        log = log_request.resource_logs[0].scope_logs[0].log_records[0]
        assert span.trace_id == log.trace_id and span.span_id == log.span_id
        attrs = {attribute.key: attribute.value.string_value for attribute in trace_request.resource_spans[0].resource.attributes}
        assert attrs == {"service.name": "pnballie-api", "deployment.environment.name": "preview"}
    finally:
        runtime.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
