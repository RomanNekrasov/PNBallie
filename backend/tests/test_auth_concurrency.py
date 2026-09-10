from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException, Request
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth import GroupContext, rate_limit, token_hash
from app.models import AuthThrottle, Group, Invite, Membership, User, utc_now
from app.routers.groups import JoinGroup, join_group, remove_member


def file_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent.db'}", connect_args={"check_same_thread": False, "timeout": 10})
    SQLModel.metadata.create_all(engine)
    return engine


def test_concurrent_rate_limit_never_overshoots(tmp_path):
    engine = file_engine(tmp_path)
    barrier = Barrier(12)

    def attempt(_):
        with Session(engine) as session:
            barrier.wait()
            try:
                rate_limit(session, "shared-key", 5, 900)
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(attempt, range(12)))
    assert results.count(200) == 5 and results.count(429) == 7
    with Session(engine) as session:
        assert session.get(AuthThrottle, token_hash("shared-key")).attempts == 5
    engine.dispose()


def seed_users(engine):
    with Session(engine) as session:
        session.add(Group(id=1, name="Pool"))
        session.add_all([User(id=i, email=f"person{i}@example.org", display_name=f"Person {i}") for i in range(1, 4)])
        session.commit()


def test_concurrent_join_consumes_single_use_invitation_once(tmp_path):
    from datetime import timedelta

    engine = file_engine(tmp_path)
    seed_users(engine)
    with Session(engine) as session:
        session.add(Invite(id=1, group_id=1, created_by=1, code_hash=token_hash("a-secret-code"), expires_at=utc_now() + timedelta(hours=1), max_uses=1))
        session.commit()
    barrier = Barrier(2)

    def join(user_id):
        with Session(engine) as session:
            user = session.get(User, user_id)
            barrier.wait()
            try:
                join_group(JoinGroup(code="a-secret-code"), Request({"type": "http", "client": ("test", 1000), "headers": []}), user, session)
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(join, [2, 3]))
    assert sorted(results) == [200, 409]
    with Session(engine) as session:
        assert session.get(Invite, 1).uses == 1
        assert len(session.exec(select(Membership)).all()) == 1
    engine.dispose()


def test_concurrent_admin_removal_keeps_an_admin(tmp_path):
    engine = file_engine(tmp_path)
    seed_users(engine)
    with Session(engine) as session:
        session.add_all([Membership(group_id=1, user_id=i, role="admin") for i in (1, 2)])
        session.commit()
    barrier = Barrier(2)

    def remove(user_id):
        with Session(engine) as session:
            group = GroupContext(id=1, role="admin", user=session.get(User, user_id))
            barrier.wait()
            try:
                remove_member(3 - user_id, group, session)
                return 204
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(remove, [1, 2]))
    assert sorted(results) == [204, 403]
    with Session(engine) as session:
        admins = session.exec(select(Membership).where(Membership.role == "admin")).all()
        assert len(admins) == 1
    engine.dispose()
