"""Run with ``python -m app.avatar_worker`` beside the API, against its SQLite DB.

Database claims are atomic across worker processes. Renewed leases allow safe
recovery after a crash; fencing tokens prevent an expired worker publishing.
"""

import argparse
import threading
import time
from contextvars import copy_context
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import Engine, and_, or_, update
from sqlmodel import Session, select

from app.avatar_images import InvalidAvatarImage, validate_transparent_png
from app.avatar_models import AvatarJob, PlayerAvatar, utcnow
from app.avatar_providers import AvatarProvider, AvatarProviderError
from app.database import engine
from app.models import Membership, Player, as_utc
from app.telemetry import (
    WORKER_SERVICE,
    Runtime,
    SpanKind,
    event,
    job_event,
    provider_label,
    span_result,
)

telemetry = Runtime(WORKER_SERVICE, engine)
MAX_ATTEMPTS = 3
LEASE_SECONDS = 120
SOURCE_RETENTION = timedelta(hours=24)


def _eligible(now: datetime):
    return and_(AvatarJob.attempts < MAX_ATTEMPTS, or_(
        and_(AvatarJob.status == "queued", AvatarJob.available_at <= now),
        and_(AvatarJob.status == "processing", AvatarJob.leased_until <= now),
    ))


def _terminal_values(status: str, error: str | None, now: datetime) -> dict:
    return {"status": status, "error": error, "source_png": None,
            "active_player_id": None, "lease_token": None,
            "leased_until": None, "updated_at": now}


def claim_job(database: Engine, *, now: datetime | None = None) -> AvatarJob | None:
    now = now or utcnow()
    with Session(database) as session:
        # Clean up abandoned uploads even when the queue cannot be processed.
        expired = session.exec(update(AvatarJob).where(or_(
            and_(AvatarJob.status == "queued", AvatarJob.created_at < now - SOURCE_RETENTION),
            and_(AvatarJob.status == "processing", AvatarJob.leased_until <= now,
                 or_(AvatarJob.attempts >= MAX_ATTEMPTS,
                     AvatarJob.created_at < now - SOURCE_RETENTION)),
        )).values(**_terminal_values("failed", "De opdracht is verlopen. Upload de foto opnieuw.", now)))
        session.commit()
        if expired.rowcount:
            job_event(telemetry, "other", "expired", count=expired.rowcount)
            telemetry.log("avatar.job.expired", provider="other", outcome="expired", count=expired.rowcount)
        job_id = session.exec(select(AvatarJob.id).where(_eligible(now))
                              .order_by(AvatarJob.created_at, AvatarJob.id).limit(1)).first()
        if job_id is None:
            return None
        token = str(uuid4())
        result = session.exec(update(AvatarJob).where(AvatarJob.id == job_id, _eligible(now)).values(
            status="processing", attempts=AvatarJob.attempts + 1, error=None,
            lease_token=token, leased_until=now + timedelta(seconds=LEASE_SECONDS), updated_at=now,
        ))
        session.commit()
        if result.rowcount != 1:
            return None
        job = session.get(AvatarJob, job_id)
        session.expunge(job)
        return job


def renew_lease(database: Engine, job: AvatarJob) -> bool:
    now = utcnow()
    with Session(database) as session:
        result = session.exec(update(AvatarJob).where(
            AvatarJob.id == job.id, AvatarJob.status == "processing",
            AvatarJob.lease_token == job.lease_token, AvatarJob.leased_until > now,
        ).values(leased_until=now + timedelta(seconds=LEASE_SECONDS), updated_at=now))
        session.commit()
        return result.rowcount == 1


def authorized(session: Session, job: AvatarJob) -> bool:
    player = session.get(Player, job.player_id)
    return bool(player and player.is_active and player.group_id == job.group_id
                and player.user_id == job.user_id
                and session.get(Membership, (job.group_id, job.user_id)))


def complete_job(database: Engine, job: AvatarJob, png: bytes) -> bool:
    now = utcnow()
    with Session(database) as session:
        # Take the write lock before authorization and PNG replacement, then do
        # all writes in the same transaction. Cancellation/rebinding wins safely.
        result = session.exec(update(AvatarJob).where(
            AvatarJob.id == job.id, AvatarJob.status == "processing",
            AvatarJob.lease_token == job.lease_token, AvatarJob.leased_until > now,
        ).values(**_terminal_values("succeeded", None, now)))
        if result.rowcount != 1:
            session.rollback()
            return False
        if not authorized(session, job):
            session.exec(update(AvatarJob).where(AvatarJob.id == job.id).values(
                status="cancelled", error="Je hebt geen toegang meer tot dit spelersprofiel.",
            ))
            session.commit()
            return False
        avatar = session.get(PlayerAvatar, job.player_id)
        if avatar is None:
            avatar = PlayerAvatar(player_id=job.player_id, group_id=job.group_id,
                                  version=job.id, png=png, updated_at=now)
        else:
            avatar.png = png
            avatar.version = job.id
            avatar.updated_at = now
        session.add(avatar)
        session.commit()
        return True


def fail_job(database: Engine, job: AvatarJob, error: str, *, retryable: bool = False):
    now = utcnow()
    retry = retryable and job.attempts < MAX_ATTEMPTS and as_utc(job.created_at) > now - SOURCE_RETENTION
    values = {"status": "queued", "error": error, "lease_token": None, "leased_until": None,
              "available_at": now + timedelta(seconds=30 * 2 ** (job.attempts - 1)),
              "updated_at": now} if retry else _terminal_values("failed", error, now)
    with Session(database) as session:
        result = session.exec(update(AvatarJob).where(
            AvatarJob.id == job.id, AvatarJob.status == "processing",
            AvatarJob.lease_token == job.lease_token,
        ).values(**values))
        session.commit()
        return ("retry" if retry else "failure") if result.rowcount else "fenced"


class LeaseHeartbeat:
    def __init__(self, database: Engine, job: AvatarJob):
        self.database, self.job = database, job
        self.stopped = threading.Event()
        context = copy_context()
        self.thread = threading.Thread(target=lambda: context.run(self._run), daemon=True)

    def _run(self):
        while not self.stopped.wait(LEASE_SECONDS / 3):
            try:
                if not renew_lease(self.database, self.job):
                    return
                telemetry.refresh_queue()
            except Exception:
                # Never log model exceptions, request bodies or photograph data.
                event("avatar.lease.failed", level="WARNING", error_type="lease_lost")
                return

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stopped.set()
        self.thread.join(timeout=5)


def run_once(database: Engine = engine, provider: AvatarProvider | None = None) -> bool:
    telemetry.database = database
    telemetry.refresh_queue()
    job = claim_job(database)
    if job is None:
        return False
    telemetry.refresh_queue()
    started = time.monotonic()
    wait = max(0, (utcnow() - as_utc(job.created_at)).total_seconds())
    outcome, error_type = "failure", "none"
    with telemetry.span("avatar.process", parent=job.traceparent or "", root=True,
                        kind=SpanKind.CONSUMER, attributes={"avatar.provider": provider_label(job.provider), "avatar.attempt": job.attempts}) as span:
        event("avatar.job.claimed", provider=job.provider, attempt=job.attempts, wait_seconds=wait)
        try:
            with Session(database) as session:
                permitted = authorized(session, job)
            if not permitted:
                error_type = "not_authorized"
                outcome = fail_job(database, job, "Je hebt geen toegang meer tot dit spelersprofiel.")
                return True
            with LeaseHeartbeat(database, job):
                try:
                    if job.source_png is None:
                        raise AvatarProviderError("De bronfoto is niet meer beschikbaar.")
                    png = (provider or AvatarProvider()).generate(
                        source_png=job.source_png, provider=job.provider,
                        cloud_consent=job.cloud_consent, job_id=job.id,
                    )
                    published = complete_job(database, job, validate_transparent_png(png))
                    if published:
                        outcome = "success"
                    else:
                        with Session(database) as session:
                            current = session.get(AvatarJob, job.id)
                            outcome = "cancelled" if current and current.status == "cancelled" else "fenced"
                except AvatarProviderError as exc:
                    error_type = "provider_error"
                    outcome = fail_job(database, job, str(exc), retryable=exc.retryable)
                except InvalidAvatarImage as exc:
                    error_type = "invalid_image"
                    outcome = fail_job(database, job, str(exc))
                except Exception:
                    error_type = "unexpected"
                    outcome = fail_job(database, job, "De avatar kon niet worden gemaakt. Probeer later opnieuw.")
        finally:
            duration = time.monotonic() - started
            span_result(span, outcome=outcome, error=error_type)
            job_event(telemetry, job.provider, outcome, duration=duration, wait=wait)
            event("avatar.job.finished", provider=job.provider, outcome=outcome,
                  error_type=error_type, attempt=job.attempts, duration_seconds=duration)
            telemetry.refresh_queue()
    return True


def main():
    parser = argparse.ArgumentParser(description="Process PNBallie avatar jobs")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    args = parser.parse_args()
    telemetry.configure()
    telemetry.worker_metrics()
    try:
        while True:
            try:
                processed = run_once()
            except Exception:
                telemetry.log("worker.iteration.failed", level="ERROR", error_type="unexpected")
                processed = False
            if args.once:
                break
            if not processed:
                time.sleep(5)
    finally:
        telemetry.close()


if __name__ == "__main__":
    main()
