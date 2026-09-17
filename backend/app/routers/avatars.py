from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth import GroupContext, require_group, require_verified_user
from app.avatar_images import (
    ALLOWED_MIME,
    MAX_UPLOAD_BYTES,
    InvalidAvatarImage,
    normalize_upload,
)
from app.avatar_models import AvatarJob, AvatarJobRead, PlayerAvatar, read_job, utcnow
from app.avatar_originals import store_original
from app.avatar_providers import AvatarSettings
from app.avatar_readiness import CAPACITY_MESSAGE, UNAVAILABLE_MESSAGE, local_status
from app.avatar_worker import SOURCE_RETENTION, _terminal_values
from app.database import get_session
from app.models import Membership, Player, User
from app.telemetry import API_SERVICE, Runtime, current_traceparent, event, job_event

# HTTP span context is supplied by the application middleware.
telemetry = Runtime(API_SERVICE)

router = APIRouter(prefix="/avatars", tags=["avatars"])
MAX_PLAYER_GENERATIONS = 3


def check_generation_quota(session: Session, player_id: int, user_id: int) -> None:
    total = session.exec(select(func.count()).select_from(AvatarJob).where(
        AvatarJob.player_id == player_id,
    )).one()
    if total >= MAX_PLAYER_GENERATIONS:
        raise HTTPException(429, "Je kunt maximaal drie avatars voor dit spelersprofiel aanvragen.")
    recent = session.exec(select(func.count()).select_from(AvatarJob).where(
        AvatarJob.user_id == user_id, AvatarJob.created_at > utcnow() - SOURCE_RETENTION,
    )).one()
    if recent >= 5:
        raise HTTPException(429, "Je kunt maximaal vijf avatars per 24 uur aanvragen.")


def own_player(group: GroupContext, session: Session) -> Player:
    player = session.exec(select(Player).where(
        Player.group_id == group.id, Player.user_id == group.user.id, Player.is_active.is_(True),
    )).first()
    if player is None:
        raise HTTPException(409, "Koppel eerst je eigen spelersprofiel aan deze groep.")
    return player


@router.get("/config")
async def configuration(group: GroupContext = Depends(require_group)):
    config = AvatarSettings.from_env()
    state = await local_status(config) if config.default_provider == "local" else "unknown"
    return {"available": config.available(config.default_provider),
            "default_provider": config.default_provider,
            "max_upload_bytes": MAX_UPLOAD_BYTES, "local_status": state,
            "local_style": config.local_style}


@router.post("/me/jobs", status_code=202, response_model=AvatarJobRead)
async def upload(request: Request, provider: Literal["local", "openai", "azure"] | None = None, group: GroupContext = Depends(require_group),
                 session: Session = Depends(get_session)):
    player = own_player(group, session)
    config = AvatarSettings.from_env()
    if provider is not None and provider != config.default_provider:
        raise HTTPException(409, "Ververs de pagina en probeer opnieuw.")
    provider = config.default_provider
    if not config.available(provider):
        raise HTTPException(503, "Deze afbeeldingsdienst is nog niet ingesteld.")
    if provider == "local":
        state = await local_status(config)
        if state in {"capacity", "unavailable"}:
            raise HTTPException(503, CAPACITY_MESSAGE if state == "capacity" else UNAVAILABLE_MESSAGE)
    if session.exec(select(AvatarJob.id).where(AvatarJob.active_player_id == player.id)).first():
        raise HTTPException(409, "Er wordt al een avatar voor je gemaakt.")
    check_generation_quota(session, player.id, group.user.id)
    mime = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(415, "Gebruik een JPEG-, PNG-, WebP- of HEIC/HEIF-foto.")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "De foto mag maximaal 20 MB groot zijn.")
    try:
        source = normalize_upload(bytes(raw), mime)
    except InvalidAvatarImage as exc:
        raise HTTPException(422, str(exc)) from exc
    # Decode before opening a write transaction. Recheck authorization and quota
    # under SQLite's write lock, so simultaneous uploads cannot bypass either
    # the lifetime per-player quota or the daily per-user limit.
    group_id, user_id, player_id = group.id, group.user.id, player.id
    session.rollback()
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    current = session.get(Player, player_id)
    if not current or not current.is_active or current.group_id != group_id or current.user_id != user_id \
            or not session.get(Membership, (group_id, user_id)):
        session.rollback()
        raise HTTPException(409, "Je hebt geen toegang meer tot dit spelersprofiel.")
    try:
        check_generation_quota(session, player_id, user_id)
    except HTTPException:
        session.rollback()
        raise
    job = AvatarJob(group_id=group_id, user_id=user_id, player_id=player_id,
                    active_player_id=player_id, provider=provider,
                    # Legacy worker processing flag; this is not a checkbox-consent record.
                    cloud_consent=provider in {"azure", "openai"},
                    source_png=source, traceparent=current_traceparent())
    original = None
    try:
        original = store_original(bytes(raw), mime, group_id=group_id, player_id=player_id, job_id=job.id)
        session.add(job)
        session.commit()
    except OSError as exc:
        session.rollback()
        if original is not None:
            original.unlink(missing_ok=True)
        raise HTTPException(503, "De foto kon niet worden opgeslagen. Probeer later opnieuw.") from exc
    except IntegrityError as exc:
        session.rollback()
        if original is not None:
            original.unlink(missing_ok=True)
        raise HTTPException(409, "Er wordt al een avatar voor je gemaakt.") from exc
    except Exception:
        session.rollback()
        if original is not None:
            original.unlink(missing_ok=True)
        raise
    session.refresh(job)
    job_event(telemetry, job.provider, "enqueued")
    event("avatar.job.enqueued", provider=job.provider, outcome="enqueued")
    return read_job(job, session)


@router.get("/me/latest", response_model=AvatarJobRead | None)
def latest(group: GroupContext = Depends(require_group), session: Session = Depends(get_session)):
    player = own_player(group, session)
    job = session.exec(select(AvatarJob).where(
        AvatarJob.group_id == group.id, AvatarJob.user_id == group.user.id,
        AvatarJob.player_id == player.id,
    ).order_by(AvatarJob.created_at.desc(), AvatarJob.id.desc()).limit(1)).first()
    return read_job(job, session) if job else None


def own_job(job_id: str, group: GroupContext, session: Session) -> AvatarJob:
    job = session.get(AvatarJob, job_id)
    if not job or job.group_id != group.id or job.user_id != group.user.id:
        raise HTTPException(404, "Opdracht niet gevonden.")
    return job


@router.get("/jobs/{job_id}", response_model=AvatarJobRead)
def job_status(job_id: str, group: GroupContext = Depends(require_group),
               session: Session = Depends(get_session)):
    return read_job(own_job(job_id, group, session), session)


@router.delete("/jobs/{job_id}", response_model=AvatarJobRead)
def cancel(job_id: str, group: GroupContext = Depends(require_group),
           session: Session = Depends(get_session)):
    job = own_job(job_id, group, session)
    result = session.exec(update(AvatarJob).where(AvatarJob.id == job_id,
        AvatarJob.status.in_(["queued", "processing"])).values(
            **_terminal_values("cancelled", None, utcnow())))
    session.commit()
    if result.rowcount:
        job_event(telemetry, job.provider, "cancelled")
        event("avatar.job.cancelled", provider=job.provider, outcome="cancelled")
    return read_job(session.get(AvatarJob, job_id), session)


@router.get("/players/{player_id}.png", include_in_schema=False)
def player_image(player_id: int, user: User = Depends(require_verified_user),
                 session: Session = Depends(get_session)):
    player = session.get(Player, player_id)
    # Browser image requests have cookies, but cannot set X-Group-ID. Authorize
    # against the actual player's group; never make uploaded portraits public.
    if not player or not session.get(Membership, (player.group_id, user.id)):
        raise HTTPException(404, "Avatar niet gevonden.")
    avatar = session.get(PlayerAvatar, player_id)
    if not avatar or avatar.group_id != player.group_id:
        raise HTTPException(404, "Avatar niet gevonden.")
    return Response(avatar.png, media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline; filename=avatar.png",
    })
