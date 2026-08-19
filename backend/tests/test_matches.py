import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.models import MatchCreate, MatchPlayerIn, Player
from app.routers.matches import _validate_match


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Player(id=index, name=f"Player {index}") for index in range(1, 5)])
        db.commit()
        yield db


def payload(entries: list[tuple[int, str, str]]) -> MatchCreate:
    return MatchCreate(
        orange_score=10,
        blue_score=7,
        players=[
            MatchPlayerIn(player_id=player_id, side=side, position=position)
            for player_id, side, position in entries
        ],
    )


def test_accepts_valid_1v1_and_2v2(session):
    _validate_match(payload([(1, "orange", "solo"), (2, "blue", "solo")]), session)
    _validate_match(payload([
        (1, "orange", "voor"), (2, "orange", "achter"),
        (3, "blue", "voor"), (4, "blue", "achter"),
    ]), session)


@pytest.mark.parametrize("entries, detail", [
    ([(1, "orange", "voor"), (2, "blue", "solo")], "1v1 players must use the solo position"),
    ([(1, "orange", "voor"), (2, "orange", "voor"), (3, "blue", "voor"), (4, "blue", "achter")], "Orange must have one voor and one achter player"),
    ([(1, "orange", "solo"), (99, "blue", "solo")], "Unknown player IDs: [99]"),
])
def test_rejects_malformed_formations_and_unknown_players(session, entries, detail):
    with pytest.raises(HTTPException) as error:
        _validate_match(payload(entries), session)
    assert error.value.status_code == 422
    assert error.value.detail == detail
