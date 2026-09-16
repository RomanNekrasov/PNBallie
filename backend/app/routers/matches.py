from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime
from sqlmodel import Session, select

from app.auth import GroupContext, require_group, require_group_admin
from app.database import get_session
from app.models import (
    Match,
    MatchCreate,
    MatchPlayer,
    MatchPlayerOut,
    MatchRead,
    MatchRecorder,
    Player,
    as_utc,
)

router = APIRouter(prefix="/api/matches", tags=["matches"])

VALID_SIDES = {"orange", "blue"}
VALID_POSITIONS = {"voor", "achter", "solo"}


def _validate_match(match: MatchCreate, session: Session, group_id: int = 1, retained_ids: set[int] | None = None):
    if len(match.players) not in {2, 4}:
        raise HTTPException(status_code=422, detail="A match must be 1v1 or 2v2")

    for mp in match.players:
        if mp.side not in VALID_SIDES:
            raise HTTPException(status_code=422, detail=f"Invalid side: {mp.side}")
        if mp.position not in VALID_POSITIONS:
            raise HTTPException(status_code=422, detail=f"Invalid position: {mp.position}")

    orange = [p for p in match.players if p.side == "orange"]
    blue = [p for p in match.players if p.side == "blue"]

    if len(orange) != len(blue):
        raise HTTPException(status_code=422, detail="Teams must have equal number of players")

    if len(match.players) == 2:
        if any(player.position != "solo" for player in match.players):
            raise HTTPException(status_code=422, detail="1v1 players must use the solo position")
    else:
        for side, team in (("orange", orange), ("blue", blue)):
            if {player.position for player in team} != {"voor", "achter"}:
                raise HTTPException(
                    status_code=422,
                    detail=f"{side.capitalize()} must have one voor and one achter player",
                )

    all_ids = [p.player_id for p in match.players]
    if len(all_ids) != len(set(all_ids)):
        raise HTTPException(status_code=422, detail="Duplicate players across positions")

    existing_ids = set(
        session.exec(select(Player.id).where(Player.id.in_(all_ids), Player.group_id == group_id, (Player.is_active.is_(True) | Player.id.in_(retained_ids or set())))).all()
    )
    missing_ids = sorted(set(all_ids) - existing_ids)
    if missing_ids:
        raise HTTPException(status_code=422, detail=f"Unknown player IDs: {missing_ids}")

    if match.orange_score != 10 and match.blue_score != 10:
        raise HTTPException(status_code=422, detail="One team must have a score of 10")
    if match.orange_score == match.blue_score:
        raise HTTPException(status_code=422, detail="Draws are not allowed")


def _match_to_read(match: Match, *, include_recorder: bool = False) -> MatchRead:
    return MatchRead(
        id=match.id,
        orange_score=match.orange_score,
        blue_score=match.blue_score,
        played_at=match.played_at,
        recorded_by=MatchRecorder(user_id=match.recorded_by_user_id, name=match.recorded_by_name) if include_recorder and match.recorded_by_name else None,
        players=[
            MatchPlayerOut(player_id=mp.player_id, side=mp.side, position=mp.position)
            for mp in match.players
        ],
    )


@router.get("", response_model=list[MatchRead])
def list_matches(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), group: GroupContext = Depends(require_group), session: Session = Depends(get_session)):
    matches = session.exec(
        select(Match).where(Match.group_id == group.id).order_by(Match.played_at.desc(), Match.id.desc()).offset(offset).limit(limit)
    ).all()
    return [_match_to_read(m, include_recorder=group.role == "admin") for m in matches]


@router.post("", response_model=MatchRead, status_code=201)
def create_match(match: MatchCreate, group: GroupContext = Depends(require_group), session: Session = Depends(get_session)):
    _validate_match(match, session, group.id)
    db_match = Match(
        group_id=group.id,
        recorded_by_user_id=group.user.id,
        recorded_by_name=group.user.display_name,
        orange_score=match.orange_score,
        blue_score=match.blue_score,
    )
    session.add(db_match)
    session.flush()  # get the match id

    for mp in match.players:
        db_mp = MatchPlayer(
            match_id=db_match.id,
            player_id=mp.player_id,
            side=mp.side,
            position=mp.position,
        )
        session.add(db_mp)

    session.commit()
    session.refresh(db_match)
    return _match_to_read(db_match, include_recorder=group.role == "admin")


class MatchUpdate(MatchCreate):
    played_at: AwareDatetime
    expected: MatchRead


def _locked_match(match_id: int, group_id: int, session: Session, expected: MatchRead | None = None):
    session.rollback()
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    match = session.get(Match, match_id, populate_existing=True)
    if not match or match.group_id != group_id:
        raise HTTPException(404, "Match not found")
    if expected:
        current = _match_to_read(match)
        def comparable(value):
            result = value.model_dump(exclude={"recorded_by"})
            result["players"] = sorted(result["players"], key=lambda player: player["player_id"])
            return result
        if comparable(current) != comparable(expected):
            raise HTTPException(409, "Deze wedstrijd is intussen gewijzigd. Laad de lijst opnieuw.")
    return match


@router.put("/{match_id}", response_model=MatchRead)
def update_match(match_id: int, payload: MatchUpdate, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    match = _locked_match(match_id, group.id, session, payload.expected)
    _validate_match(payload, session, group.id, {player.player_id for player in match.players})
    match.orange_score = payload.orange_score
    match.blue_score = payload.blue_score
    match.played_at = as_utc(payload.played_at)
    for player in match.players:
        session.delete(player)
    session.flush()
    for player in payload.players:
        session.add(MatchPlayer(match_id=match.id, **player.model_dump()))
    session.commit()
    session.refresh(match)
    session.expire(match, ["players"])
    return _match_to_read(match, include_recorder=True)


@router.delete("/{match_id}", status_code=204)
def delete_match(match_id: int, expected: MatchRead | None = None, group: GroupContext = Depends(require_group_admin), session: Session = Depends(get_session)):
    match = _locked_match(match_id, group.id, session, expected)
    # Delete match players first
    for mp in match.players:
        session.delete(mp)
    session.delete(match)
    session.commit()
