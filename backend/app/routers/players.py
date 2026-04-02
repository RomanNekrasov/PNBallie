from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Player, PlayerCreate, PlayerRead

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("", response_model=list[PlayerRead])
def list_players(session: Session = Depends(get_session)):
    return session.exec(select(Player).order_by(Player.name)).all()


@router.post("", response_model=PlayerRead, status_code=201)
def create_player(player: PlayerCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(Player).where(Player.name == player.name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Player name already exists")
    db_player = Player.model_validate(player)
    session.add(db_player)
    session.commit()
    session.refresh(db_player)
    return db_player


@router.delete("/{player_id}", status_code=204)
def delete_player(player_id: int, session: Session = Depends(get_session)):
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    session.delete(player)
    session.commit()
