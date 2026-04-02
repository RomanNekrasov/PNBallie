from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Match, MatchCreate, MatchPlayer, MatchPlayerOut, MatchRead

router = APIRouter(prefix="/api/matches", tags=["matches"])

VALID_SIDES = {"orange", "blue"}
VALID_POSITIONS = {"voor", "achter", "solo"}


def _validate_match(match: MatchCreate):
    if not match.players:
        raise HTTPException(status_code=422, detail="At least 2 players required")

    for mp in match.players:
        if mp.side not in VALID_SIDES:
            raise HTTPException(status_code=422, detail=f"Invalid side: {mp.side}")
        if mp.position not in VALID_POSITIONS:
            raise HTTPException(status_code=422, detail=f"Invalid position: {mp.position}")

    orange = [p for p in match.players if p.side == "orange"]
    blue = [p for p in match.players if p.side == "blue"]

    if not orange:
        raise HTTPException(status_code=422, detail="At least 1 orange player required")
    if not blue:
        raise HTTPException(status_code=422, detail="At least 1 blue player required")
    if len(orange) != len(blue):
        raise HTTPException(status_code=422, detail="Teams must have equal number of players")

    all_ids = [p.player_id for p in match.players]
    if len(all_ids) != len(set(all_ids)):
        raise HTTPException(status_code=422, detail="Duplicate players across positions")

    if match.orange_score != 10 and match.blue_score != 10:
        raise HTTPException(status_code=422, detail="One team must have a score of 10")
    if match.orange_score == match.blue_score:
        raise HTTPException(status_code=422, detail="Draws are not allowed")


def _match_to_read(match: Match) -> MatchRead:
    return MatchRead(
        id=match.id,
        orange_score=match.orange_score,
        blue_score=match.blue_score,
        played_at=match.played_at,
        players=[
            MatchPlayerOut(player_id=mp.player_id, side=mp.side, position=mp.position)
            for mp in match.players
        ],
    )


@router.get("", response_model=list[MatchRead])
def list_matches(session: Session = Depends(get_session)):
    matches = session.exec(select(Match).order_by(Match.played_at.desc()).limit(50)).all()
    return [_match_to_read(m) for m in matches]


@router.post("", response_model=MatchRead, status_code=201)
def create_match(match: MatchCreate, session: Session = Depends(get_session)):
    _validate_match(match)
    db_match = Match(
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
    return _match_to_read(db_match)


@router.delete("/{match_id}", status_code=204)
def delete_match(match_id: int, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    # Delete match players first
    for mp in match.players:
        session.delete(mp)
    session.delete(match)
    session.commit()
