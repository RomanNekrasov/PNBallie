from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlmodel import SQLModel

from alembic import command
from app import avatar_models, models  # noqa: F401 – register every table


def migration_config(path, monkeypatch):
    url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", url)
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), sa.create_engine(url)


def test_upgrade_preserves_legacy_history_and_matches_metadata(tmp_path, monkeypatch):
    config, engine = migration_config(tmp_path / "migrated.db", monkeypatch)
    command.upgrade(config, "2895eb84caa9")
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO player (id,name,created_at) VALUES (11,'Historic A','2026-01-01 12:00:00'),(12,'Historic B','2026-01-02 13:00:00')"))
        connection.execute(sa.text('INSERT INTO "match" (id,orange_score,blue_score,played_at) VALUES (21,10,6,\'2026-07-01 11:30:00\')'))
        connection.execute(sa.text("INSERT INTO match_player (id,match_id,player_id,side,position) VALUES (31,21,11,'orange','solo'),(32,21,12,'blue','solo')"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT id,name,group_id,user_id,is_active FROM player ORDER BY id")).all() == [(11, "Historic A", 1, None, 1), (12, "Historic B", 1, None, 1)]
        assert connection.execute(sa.text('SELECT id,orange_score,blue_score,played_at,group_id FROM "match"')).one() == (21, 10, 6, "2026-07-01 11:30:00", 1)
        assert connection.execute(sa.text("SELECT COUNT(*) FROM match_player")).scalar() == 2
        assert connection.execute(sa.text("SELECT COUNT(*) FROM membership")).scalar() == 0
        assert connection.execute(sa.text('SELECT is_legacy FROM "group" WHERE id=1')).scalar() == 1
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        assert compare_metadata(MigrationContext.configure(connection), SQLModel.metadata) == []
    # Empty new-group history can be rolled back to the legacy schema without
    # rewriting historical timestamps, player identifiers, or match records.
    command.downgrade(config, "2895eb84caa9")
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT id,name FROM player ORDER BY id")).all() == [(11, "Historic A"), (12, "Historic B")]
        assert connection.execute(sa.text("SELECT COUNT(*) FROM match_player")).scalar() == 2
    engine.dispose()


def test_downgrade_refuses_to_merge_distinct_groups(tmp_path, monkeypatch):
    config, engine = migration_config(tmp_path / "guarded.db", monkeypatch)
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(sa.text('INSERT INTO "group" (name,is_legacy,created_at) VALUES (\'Separate pool\',0,\'2026-09-01 12:00:00\')'))
    with pytest.raises(RuntimeError, match="isolated groups"):
        command.downgrade(config, "2895eb84caa9")
    engine.dispose()
