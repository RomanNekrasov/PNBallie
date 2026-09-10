"""Opt-in observability with an explicit, non-personal data contract.

No automatic HTTP/SQL instrumentation is used. Routes are templates, never URLs.
Only this module's bounded event schema is exported; raw library messages and
exception text are discarded. Telemetry failures cannot fail application work.
"""

import json
import logging
import os
import re
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException, Response
from opentelemetry import trace
from opentelemetry._logs import LogRecord, SeverityNumber
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    start_http_server,
)
from sqlalchemy import func
from sqlmodel import Session, select

API_SERVICE = "pnballie-api"
WORKER_SERVICE = "pnballie-avatar-worker"
INFERENCE_SERVICE = "pnballie-avatar-inference"
SERVICES = {API_SERVICE, WORKER_SERVICE, INFERENCE_SERVICE}
PROVIDERS = {"local", "openai"}
OUTCOMES = {"success", "failure", "retry", "cancelled", "fenced", "expired", "enqueued", "unavailable"}
ERRORS = {"none", "server_error", "provider_error", "invalid_image", "not_authorized", "unexpected", "unavailable", "lease_lost"}
EVENTS = {"http.request", "avatar.job.enqueued", "avatar.job.claimed", "avatar.job.finished", "avatar.job.cancelled", "avatar.job.expired", "avatar.lease.failed", "avatar.provider.finished", "avatar.inference.finished", "avatar.model.loading", "avatar.model.loaded", "avatar.model.released", "avatar.model.progress", "telemetry.disabled", "worker.iteration.failed", "runtime.warning", "runtime.error"}
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
TRACEPARENT = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$")
_REGISTRY = CollectorRegistry()
_current_runtime: ContextVar["Runtime | None"] = ContextVar("pnballie_runtime", default=None)
_logger = logging.getLogger("pnballie.events")
_default_service = API_SERVICE
_propagator = TraceContextTextMapPropagator()

HTTP_REQUESTS = Counter("pnballie_http_requests_total", "Completed HTTP requests", ["service", "method", "route", "status_code"], registry=_REGISTRY)
HTTP_DURATION = Histogram("pnballie_http_request_duration_seconds", "HTTP response latency", ["service", "method", "route"], buckets=(.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60, 300, 1800, 3600), registry=_REGISTRY)
JOBS = Counter("pnballie_avatar_jobs_total", "Avatar lifecycle transitions", ["service", "provider", "outcome"], registry=_REGISTRY)
JOB_DURATION = Histogram("pnballie_avatar_job_duration_seconds", "Avatar processing attempt latency", ["service", "provider", "outcome"], buckets=(1, 5, 10, 30, 60, 300, 600, 1800, 3600), registry=_REGISTRY)
QUEUE_WAIT = Histogram("pnballie_avatar_queue_wait_seconds", "Age of avatar jobs when claimed", ["service", "provider"], buckets=(1, 5, 15, 60, 300, 900, 3600, 21600, 86400), registry=_REGISTRY)
QUEUE_JOBS = Gauge("pnballie_avatar_queue_jobs", "Durable pending avatar jobs", ["service", "provider", "state"], registry=_REGISTRY)
QUEUE_OLDEST = Gauge("pnballie_avatar_oldest_queued_seconds", "Age of oldest queued avatar job", ["service"], registry=_REGISTRY)
PROVIDER_REQUESTS = Counter("pnballie_avatar_provider_requests_total", "Avatar provider attempts", ["service", "provider", "outcome"], registry=_REGISTRY)
PROVIDER_DURATION = Histogram("pnballie_avatar_provider_duration_seconds", "Avatar provider latency", ["service", "provider", "outcome"], buckets=(1, 5, 10, 30, 60, 300, 600, 1800, 3600), registry=_REGISTRY)


def enabled(name: str) -> bool:
    return os.getenv(name, "false").lower() in {"true", "1", "yes"}


def provider_label(value: str) -> str:
    return value if value in PROVIDERS else "other"


def outcome_label(value: str) -> str:
    return value if value in OUTCOMES else "failure"


def environment() -> str:
    value = os.getenv("DEPLOYMENT_ENVIRONMENT", "").strip()
    if not value:
        for item in os.getenv("OTEL_RESOURCE_ATTRIBUTES", "").split(","):
            key, _, candidate = item.partition("=")
            if key.strip() == "deployment.environment.name":
                value = candidate.strip()
                break
    value = value or os.getenv("APP_ENV", "development")
    # Only this resource attribute is read; arbitrary environment metadata is
    # never forwarded (it can contain hostnames, credentials or account names).
    return value if value in {"development", "test", "preview", "staging", "production"} else "other"


def parent_context(traceparent: str | None) -> Context:
    if not traceparent or not TRACEPARENT.fullmatch(traceparent):
        return Context()
    context = _propagator.extract({"traceparent": traceparent})
    return context if trace.get_current_span(context).get_span_context().is_valid else Context()


def current_traceparent() -> str | None:
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None
    return f"00-{context.trace_id:032x}-{context.span_id:016x}-{int(context.trace_flags) & 1:02x}"


def trace_headers() -> dict[str, str]:
    value = current_traceparent()
    return {"traceparent": value} if value else {}


def span_result(span, *, outcome: str, error: str = "none", **attributes) -> None:
    try:
        span.set_attribute("pnballie.outcome", outcome_label(outcome))
        if error in ERRORS and error != "none":
            span.set_attribute("error.type", error)
        for key, value in attributes.items():
            if key in {"http.response.status_code", "http.route", "avatar.provider", "avatar.attempt"}:
                span.set_attribute(key, value)
        if outcome in {"failure", "retry", "unavailable"}:
            span.set_status(Status(StatusCode.ERROR))
    except Exception:
        pass


def _safe_payload(event: str, service: str, level: str, fields: dict) -> dict:
    result = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": level,
              "service": service if service in SERVICES else API_SERVICE,
              "environment": environment(), "event": event if event in EVENTS else "runtime.warning"}
    for key, value in fields.items():
        if key == "provider":
            result[key] = provider_label(value)
        elif key == "outcome":
            result[key] = outcome_label(value)
        elif key == "error_type":
            result[key] = value if value in ERRORS else "unexpected"
        elif key == "method":
            result[key] = value if value in METHODS else "OTHER"
        elif key == "route" and value in _ROUTES:
            result[key] = value
        elif key == "stage" and value in {"edit", "layered"}:
            result[key] = value
        elif key in {"duration_seconds", "wait_seconds", "count", "attempt", "step", "total", "status_code"} and isinstance(value, (int, float)):
            result[key] = round(max(0, min(value, 86400000)), 4)
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        result.update(trace_id=f"{context.trace_id:032x}", span_id=f"{context.span_id:016x}")
    return result


# Route names are registered from code when each FastAPI app is installed.
# Unknown requests are aggregated in one bucket, never reflected into telemetry.
_ROUTES = {"unmatched"}


class SafeJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "pnballie_payload", None)
        if not isinstance(payload, dict):
            runtime = _current_runtime.get()
            payload = _safe_payload("runtime.error" if record.levelno >= logging.ERROR else "runtime.warning", runtime.service if runtime else _default_service, record.levelname, {})
        # Never format record.msg, args, exc_info or stack_info from libraries.
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


class SafeConsoleFilter(logging.Filter):
    def filter(self, record):
        return hasattr(record, "pnballie_payload") or record.levelno >= logging.WARNING


def configure_logging(stream=None, *, service=API_SERVICE) -> None:
    global _default_service
    _default_service = service
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(SafeJSONFormatter())
    handler.addFilter(SafeConsoleFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.captureWarnings(True)
    logging.raiseExceptions = False
    for name in ("uvicorn", "uvicorn.error", "httpx", "httpcore", "opentelemetry", "transformers", "diffusers", "torch"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def event(name: str, *, service: str | None = None, level: str = "INFO", **fields) -> None:
    """Export only explicit safe fields; never pass exceptions or arbitrary text."""
    try:
        runtime = _current_runtime.get()
        service = service or (runtime.service if runtime else _default_service)
        payload = _safe_payload(name, service, level, fields)
        _logger.log(getattr(logging, level, logging.INFO), "", extra={"pnballie_payload": payload})
        if runtime is not None and runtime.log_writer is not None:
            runtime.log_writer.emit(LogRecord(
                timestamp=time.time_ns(), body=payload, event_name=payload["event"],
                severity_text=level, severity_number={"WARNING": SeverityNumber.WARN, "ERROR": SeverityNumber.ERROR}.get(level, SeverityNumber.INFO),
                attributes={"event.name": payload["event"]},
            ))
    except Exception:
        pass


class Runtime:
    def __init__(self, service: str, database=None):
        self.service = service
        self.database = database
        self.tracer = trace.NoOpTracerProvider().get_tracer("pnballie")
        self.tracer_provider = None
        self.log_provider = None
        self.log_writer = None
        self.metrics_server = None
        self.configured = False

    def configure(self, *, console_stream=None) -> None:
        if self.configured:
            return
        self.configured = True
        try:
            configure_logging(console_stream, service=self.service)
        except Exception:
            pass
        if not enabled("OTEL_ENABLED"):
            return
        try:
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.monitoring.svc.cluster.local:4318").rstrip("/")
            parsed = urlparse(endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Invalid exporter endpoint")
            requested = os.getenv("OTEL_SERVICE_NAME", self.service)
            service = requested if requested in SERVICES else self.service
            resource = Resource({"service.name": service, "deployment.environment.name": environment()})
            ratio = max(0, min(1, float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))))
            self.tracer_provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(ratio)))
            self.tracer_provider.add_span_processor(BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", timeout=2),
                max_queue_size=2048, max_export_batch_size=256,
                schedule_delay_millis=1000, export_timeout_millis=2000,
            ))
            self.tracer = self.tracer_provider.get_tracer("pnballie")
            self.log_provider = LoggerProvider(resource=resource)
            self.log_provider.add_log_record_processor(BatchLogRecordProcessor(
                OTLPLogExporter(endpoint=f"{endpoint}/v1/logs", timeout=2),
                max_queue_size=2048, max_export_batch_size=256,
                schedule_delay_millis=1000, export_timeout_millis=2000,
            ))
            self.log_writer = self.log_provider.get_logger("pnballie")
        except Exception:
            self.tracer = trace.NoOpTracerProvider().get_tracer("pnballie")
            self.log_writer = None
            event("telemetry.disabled", service=self.service, level="WARNING")

    @contextmanager
    def span(self, name: str, *, parent: str | None = None, root: bool = False,
             kind=SpanKind.INTERNAL, attributes=None):
        token = _current_runtime.set(self)
        manager = None
        span = trace.INVALID_SPAN
        try:
            try:
                context = parent_context(parent) if parent is not None or root else None
                manager = self.tracer.start_as_current_span(name, context=context, kind=kind,
                    attributes=attributes or {}, record_exception=False, set_status_on_exception=False)
                span = manager.__enter__()
            except Exception:
                manager = None
            yield span
        finally:
            if manager is not None:
                try:
                    manager.__exit__(None, None, None)
                except Exception:
                    pass
            _current_runtime.reset(token)

    def log(self, name: str, **fields) -> None:
        token = _current_runtime.set(self)
        try:
            event(name, **fields)
        finally:
            _current_runtime.reset(token)

    def close(self) -> None:
        if self.metrics_server is not None:
            try:
                self.metrics_server.shutdown()
                self.metrics_server.server_close()
            except Exception:
                pass
            self.metrics_server = None
        for provider in (self.log_provider, self.tracer_provider):
            if provider is not None:
                try:
                    provider.shutdown()
                except Exception:
                    pass
        self.tracer_provider = self.log_provider = self.log_writer = None
        self.tracer = trace.NoOpTracerProvider().get_tracer("pnballie")
        self.configured = False

    def refresh_queue(self) -> None:
        if not enabled("METRICS_ENABLED") or self.database is None:
            return
        try:
            from app.avatar_models import AvatarJob
            from app.models import as_utc, utc_now

            counts = {(provider, state): 0 for provider in (*sorted(PROVIDERS), "other") for state in ("queued", "processing")}
            with Session(self.database) as session:
                rows = session.exec(select(AvatarJob.provider, AvatarJob.status, func.count()).where(AvatarJob.status.in_(["queued", "processing"])).group_by(AvatarJob.provider, AvatarJob.status)).all()
                oldest = session.exec(select(func.min(AvatarJob.created_at)).where(AvatarJob.status == "queued")).one()
            for provider, state, count in rows:
                counts[(provider_label(provider), state)] += count
            for (provider, state), count in counts.items():
                QUEUE_JOBS.labels(self.service, provider, state).set(count)
            QUEUE_OLDEST.labels(self.service).set(max(0, (utc_now() - as_utc(oldest)).total_seconds()) if oldest else 0)
        except Exception:
            # A metrics scrape may race with a migration or encounter a DB lock.
            # Never affect request handling or job processing in that case.
            pass

    def worker_metrics(self) -> None:
        if enabled("METRICS_ENABLED"):
            try:
                port = int(os.getenv("METRICS_PORT", "9101"))
                self.metrics_server, _ = start_http_server(port, addr=os.getenv("METRICS_HOST", "0.0.0.0"), registry=_REGISTRY)
            except Exception:
                event("telemetry.disabled", service=self.service, level="WARNING")


def job_event(runtime: Runtime, provider: str, outcome: str, *, duration: float | None = None, wait: float | None = None, count=1) -> None:
    try:
        if enabled("METRICS_ENABLED"):
            provider, outcome = provider_label(provider), outcome_label(outcome)
            JOBS.labels(runtime.service, provider, outcome).inc(count)
            if duration is not None:
                JOB_DURATION.labels(runtime.service, provider, outcome).observe(max(0, duration))
            if wait is not None:
                QUEUE_WAIT.labels(runtime.service, provider).observe(max(0, wait))
    except Exception:
        pass


@contextmanager
def operation_span(name: str, *, kind=SpanKind.INTERNAL, attributes=None):
    runtime = _current_runtime.get() or Runtime(WORKER_SERVICE)
    with runtime.span(name, kind=kind, attributes=attributes) as span:
        yield span


def provider_finished(provider: str, outcome: str, duration: float) -> None:
    try:
        runtime = _current_runtime.get()
        if enabled("METRICS_ENABLED"):
            service = runtime.service if runtime else WORKER_SERVICE
            PROVIDER_REQUESTS.labels(service, provider_label(provider), outcome_label(outcome)).inc()
            PROVIDER_DURATION.labels(service, provider_label(provider), outcome_label(outcome)).observe(max(0, duration))
        event("avatar.provider.finished", provider=provider, outcome=outcome, duration_seconds=duration)
    except Exception:
        pass


class HTTPMiddleware:
    def __init__(self, app, runtime: Runtime, *, accept_parent=False):
        self.app, self.runtime, self.accept_parent = app, runtime, accept_parent

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") in {"/metrics", "/health/live", "/health/ready"}:
            await self.app(scope, receive, send)
            return
        started, status, failed = time.monotonic(), 500, False
        method = scope.get("method", "OTHER")
        method = method if method in METHODS else "OTHER"
        parent = None
        if self.accept_parent:
            headers = dict(scope.get("headers", []))
            parent = headers.get(b"traceparent", b"").decode("ascii", errors="ignore")
        with self.runtime.span("HTTP request", parent=parent, root=True, kind=SpanKind.SERVER, attributes={"http.request.method": method}) as span:
            async def record_send(message):
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"] if 100 <= message["status"] <= 599 else 500
                await send(message)
            try:
                await self.app(scope, receive, record_send)
            except BaseException:
                failed = True
                raise
            finally:
                route = getattr(scope.get("route"), "path", "unmatched")
                route = route if route in _ROUTES else "unmatched"
                duration = time.monotonic() - started
                status = 500 if failed else status
                span_result(span, outcome="failure" if status >= 500 else "success", error="server_error" if status >= 500 else "none", **{"http.route": route, "http.response.status_code": status})
                try:
                    span.update_name(f"{method} {route}")
                    if enabled("METRICS_ENABLED"):
                        HTTP_REQUESTS.labels(self.runtime.service, method, route, str(status)).inc()
                        HTTP_DURATION.labels(self.runtime.service, method, route).observe(duration)
                except Exception:
                    pass
                event("http.request", method=method, route=route, status_code=status, duration_seconds=duration, level="ERROR" if status >= 500 else "INFO")


def install_http(app, runtime: Runtime, *, accept_parent=False) -> None:
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            _ROUTES.add(path)
    app.add_middleware(HTTPMiddleware, runtime=runtime, accept_parent=accept_parent)

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        if not enabled("METRICS_ENABLED"):
            raise HTTPException(status_code=404, detail="Not found")
        runtime.refresh_queue()
        return Response(generate_latest(_REGISTRY), media_type=CONTENT_TYPE_LATEST, headers={"Cache-Control": "no-store"})
