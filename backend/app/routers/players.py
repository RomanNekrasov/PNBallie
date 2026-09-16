from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth import GroupContext, require_group, require_group_admin
from app.avatar_models import AvatarJob, PlayerAvatar, utcnow
from app.database import get_session
from app.models import (
    MatchPlayer,
    Membership,
    Player,
    PlayerCreate,
    PlayerRead,
    PlayerUpdate,
    ProfileUpdate,
)

router = APIRouter(prefix="/api/players", tags=["players"])


def _read(player: Player, session: Session) -> PlayerRead:
    from app.avatar_models import avatar_url

    return PlayerRead(**player.model_dump(), avatar_url=avatar_url(session, player.id))


def _player(session: Session, group_id: int, player_id: int) -> Player:
    player = session.get(Player, player_id)
    if not player or player.group_id != group_id:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


def _name(value: str) -> str:
    value = value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Player name must not be empty")
    return value


def _save(session: Session, player: Player) -> None:
    session.add(player)
    try:
        session.commit()
        session.refresh(player)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Player name or profile link already exists in this group") from exc


def _remove_replaced_profile(session: Session, previous: Player, target: Player) -> None:
    if session.exec(select(MatchPlayer).where(MatchPlayer.player_id == previous.id)).first():
        raise HTTPException(status_code=409, detail="This member already has match history on another profile; keep that profile linked")
    # Keep completed images and job history on the surviving profile. Revoke
    # leases before moving jobs so an in-flight worker cannot publish to the old ID.
    avatar = session.get(PlayerAvatar, previous.id)
    if avatar:
        if session.get(PlayerAvatar, target.id) is None:
            session.add(PlayerAvatar(player_id=target.id, group_id=target.group_id,
                                     version=avatar.version, png=avatar.png, updated_at=avatar.updated_at))
        session.delete(avatar)
    for job in session.exec(select(AvatarJob).where(AvatarJob.player_id == previous.id)).all():
        if job.status in {"queued", "processing"}:
            job.status = "cancelled"
            job.error = "Je account is aan een andere speler gekoppeld. Upload de foto opnieuw."
            job.updated_at = utcnow()
        job.source_png = None
        job.active_player_id = None
        job.lease_token = None
        job.leased_until = None
        job.player_id = target.id
        session.add(job)
    session.flush()
    session.delete(previous)
    session.flush()


@router.get("", response_model=list[PlayerRead])
def list_players(include_inactive: bool = False, group: GroupContext = Depends(require_group), session: Session = Depends(get_session)):
    query = select(Player).where(Player.group_id == group.id)
    if not include_inactive:
        query = query.where(Player.is_active.is_(True))
    return [_read(player, session) for player in session.exec(query.order_by(Player.name)).all()]


@router.get("/me", response_model=PlayerRead)
def my_player(group: GroupContext = Depends(require_group), session: Session = Depends(get_session)):
    player = session.exec(select(Player).where(Player.group_id == group.id, Player.user_id == group.user.id)).first()
    if not player:
        raise HTTPException(status_code=404, detail="No player profile is linked; ask your group administrator")
    return _read(player, session)


@router.patch("/me", response_model=PlayerRead)
def update_my_player(payload: ProfileUpdate, group: GroupContext = Depends(require_group), session: Session = Depends(get_session)):
    player = session.exec(select(Player).where(Player.group_id == group.id, Player.user_id == group.user.id)).first()
    if not player:
        raise HTTPException(status_code=404, detail="No player profile is linked; ask your group administrator")
    player.name = _name(payload.name)
    _save(session, player)
    return _read(player, session)


@router.post("", response_model=PlayerRead, status_code=201)
def create_player(payload: PlayerCreate, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    player = Player(name=payload.name, group_id=group.id)
    _save(session, player)
    return _read(player, session)


@router.patch("/{player_id}", response_model=PlayerRead)
def update_player(player_id: int, payload: PlayerUpdate, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    try:
        return _update_player(player_id, payload, group, session)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Player name or profile link already exists in this group") from exc


def _update_player(player_id: int, payload: PlayerUpdate, group: GroupContext, session: Session):
    # Serialize rebinding with avatar publication and score writes. Authorization
    # dependencies have already opened a read transaction on this SQLite session.
    session.rollback()
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    player = _player(session, group.id, player_id)
    if "name" in payload.model_fields_set:
        if payload.name is None:
            raise HTTPException(status_code=422, detail="Player name must not be null")
        player.name = _name(payload.name)
    if "is_active" in payload.model_fields_set:
        if payload.is_active is None:
            raise HTTPException(status_code=422, detail="Active status must not be null")
        player.is_active = payload.is_active
    if "user_id" in payload.model_fields_set:
        if payload.user_id is not None:
            if not session.get(Membership, (group.id, payload.user_id)):
                raise HTTPException(status_code=422, detail="The linked user must be a member of this group")
            previous = session.exec(select(Player).where(Player.group_id == group.id, Player.user_id == payload.user_id, Player.id != player.id)).first()
            if previous:
                _remove_replaced_profile(session, previous, player)
        player.user_id = payload.user_id
    _save(session, player)
    return _read(player, session)


@router.delete("/{player_id}", status_code=204)
def deactivate_player(player_id: int, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    player = _player(session, group.id, player_id)
    player.is_active = False
    _save(session, player)
