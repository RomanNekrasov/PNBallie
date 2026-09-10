import secrets
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth import (
    GroupContext,
    client_key,
    rate_limit,
    require_group,
    require_group_admin,
    require_user,
    token_hash,
)
from app.database import get_session
from app.models import Group, Invite, Membership, Player, User, as_utc, utc_now

router = APIRouter(prefix="/api/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Group name must not be empty")
        return value


class GroupRead(BaseModel):
    id: int
    name: str
    role: Literal["admin", "member"]
    player_id: int | None


class MemberRead(BaseModel):
    user_id: int
    email: str
    display_name: str
    role: Literal["admin", "member"]
    player_id: int | None


class MemberUpdate(BaseModel):
    role: Literal["admin", "member"]


class InviteCreate(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=30)
    max_uses: int | None = Field(default=None, ge=1, le=10000)


class InviteRead(BaseModel):
    id: int
    expires_at: datetime
    max_uses: int | None
    uses: int
    revoked: bool
    _utc_expires = field_validator("expires_at")(as_utc)


class InviteCreated(InviteRead):
    code: str


class JoinGroup(BaseModel):
    code: str = Field(min_length=1, max_length=200)


def group_read(session: Session, group: Group, membership: Membership) -> GroupRead:
    player = session.exec(select(Player).where(Player.group_id == group.id, Player.user_id == membership.user_id)).first()
    return GroupRead(id=group.id, name=group.name, role=membership.role, player_id=player.id if player else None)


def ensure_member_player(session: Session, group_id: int, user: User) -> Player:
    player = session.exec(select(Player).where(Player.group_id == group_id, Player.user_id == user.id)).first()
    if player:
        player.is_active = True
        session.add(player)
        return player
    names = set(session.exec(select(Player.name).where(Player.group_id == group_id)).all())
    base = user.display_name[:70]
    name, suffix = base, 2
    while name in names:
        name = f"{base} ({suffix})"
        suffix += 1
    player = Player(group_id=group_id, user_id=user.id, name=name)
    session.add(player)
    session.flush()
    return player


def _locked_admin(session: Session, group: GroupContext) -> None:
    # Serialize last-admin decisions on SQLite and row-locking databases. Recheck
    # the caller after obtaining the lock, as their role may have just changed.
    session.exec(update(Group).where(Group.id == group.id).values(name=Group.name))
    session.expire_all()
    current = session.get(Membership, (group.id, group.user.id))
    if not current or current.role != "admin":
        session.rollback()
        raise HTTPException(status_code=403, detail="Group administrator access is required")


def _member(session: Session, group_id: int, user_id: int) -> Membership:
    membership = session.get(Membership, (group_id, user_id))
    if not membership:
        raise HTTPException(status_code=404, detail="Group member not found")
    return membership


def _keep_admin(session: Session, member: Membership) -> None:
    if member.role == "admin":
        admins = session.exec(select(Membership).where(Membership.group_id == member.group_id, Membership.role == "admin")).all()
        if len(admins) <= 1:
            raise HTTPException(status_code=409, detail="A group must keep at least one administrator")


@router.get("", response_model=list[GroupRead])
def list_groups(user: User = Depends(require_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Group, Membership).join(Membership).where(Membership.user_id == user.id).order_by(Group.name, Group.id)).all()
    return [group_read(session, group, membership) for group, membership in rows]


@router.post("", response_model=GroupRead, status_code=201)
def create_group(payload: GroupCreate, user: User = Depends(require_user), session: Session = Depends(get_session)):
    rate_limit(session, f"create-group:{user.id}", 10, 3600)
    group = Group(name=payload.name)
    session.add(group)
    session.flush()
    membership = Membership(group_id=group.id, user_id=user.id, role="admin")
    session.add(membership)
    ensure_member_player(session, group.id, user)
    session.commit()
    return group_read(session, group, membership)


@router.post("/join", response_model=GroupRead)
def join_group(payload: JoinGroup, request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    rate_limit(session, f"join-user:{user.id}", 20, 900)
    rate_limit(session, f"join-ip:{client_key(request)}", 50, 900)
    invite = session.exec(select(Invite).where(Invite.code_hash == token_hash(payload.code.strip()))).first()
    if not invite or invite.revoked or as_utc(invite.expires_at) <= utc_now():
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    existing = session.get(Membership, (invite.group_id, user.id))
    if existing:
        return group_read(session, session.get(Group, invite.group_id), existing)
    updated = session.exec(update(Invite).where(Invite.id == invite.id, Invite.revoked.is_(False), Invite.expires_at > utc_now(), or_(Invite.max_uses.is_(None), Invite.uses < Invite.max_uses)).values(uses=Invite.uses + 1).execution_options(synchronize_session=False))
    if updated.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=409, detail="Invitation has reached its usage limit")
    membership = Membership(group_id=invite.group_id, user_id=user.id)
    session.add(membership)
    try:
        ensure_member_player(session, invite.group_id, user)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        existing = session.get(Membership, (invite.group_id, user.id))
        if existing:
            return group_read(session, session.get(Group, invite.group_id), existing)
        raise HTTPException(status_code=409, detail="Please try joining the group again") from exc
    return group_read(session, session.get(Group, invite.group_id), membership)


@router.get("/current", response_model=GroupRead)
def current_group(group: GroupContext = Depends(require_group), session: Session = Depends(get_session)):
    return group_read(session, session.get(Group, group.id), session.get(Membership, (group.id, group.user.id)))


@router.patch("/current", response_model=GroupRead)
def update_group(payload: GroupCreate, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    row = session.get(Group, group.id)
    row.name = payload.name
    session.add(row)
    session.commit()
    return group_read(session, row, session.get(Membership, (group.id, group.user.id)))


@router.get("/members", response_model=list[MemberRead])
def list_members(group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    rows = session.exec(select(User, Membership).join(Membership).where(Membership.group_id == group.id).order_by(User.display_name, User.id)).all()
    players = {player.user_id: player.id for player in session.exec(select(Player).where(Player.group_id == group.id)).all() if player.user_id is not None}
    return [MemberRead(user_id=user.id, email=user.email, display_name=user.display_name, role=membership.role, player_id=players.get(user.id)) for user, membership in rows]


@router.patch("/members/{user_id}", response_model=MemberRead)
def update_member(user_id: int, payload: MemberUpdate, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    _locked_admin(session, group)
    membership = _member(session, group.id, user_id)
    if membership.role == "admin" and payload.role != "admin":
        _keep_admin(session, membership)
    membership.role = payload.role
    session.add(membership)
    session.commit()
    user = session.get(User, user_id)
    player = session.exec(select(Player).where(Player.group_id == group.id, Player.user_id == user_id)).first()
    return MemberRead(user_id=user.id, email=user.email, display_name=user.display_name, role=membership.role, player_id=player.id if player else None)


@router.delete("/members/{user_id}", status_code=204)
def remove_member(user_id: int, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    _locked_admin(session, group)
    membership = _member(session, group.id, user_id)
    _keep_admin(session, membership)
    session.delete(membership)
    player = session.exec(select(Player).where(Player.group_id == group.id, Player.user_id == user_id)).first()
    if player:
        player.is_active = False
        session.add(player)
    session.commit()


@router.get("/invites", response_model=list[InviteRead])
def list_invites(group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    return session.exec(select(Invite).where(Invite.group_id == group.id).order_by(Invite.id.desc())).all()


@router.post("/invites", response_model=InviteCreated, status_code=201)
def create_invite(payload: InviteCreate, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    rate_limit(session, f"create-invite:{group.user.id}:{group.id}", 30, 3600)
    code = secrets.token_urlsafe(18)
    invite = Invite(group_id=group.id, created_by=group.user.id, code_hash=token_hash(code), expires_at=utc_now() + timedelta(days=payload.expires_in_days), max_uses=payload.max_uses)
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return InviteCreated(**invite.model_dump(), code=code)


@router.delete("/invites/{invite_id}", status_code=204)
def revoke_invite(invite_id: int, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    invite = session.get(Invite, invite_id)
    if not invite or invite.group_id != group.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invite.revoked = True
    session.add(invite)
    session.commit()
