from datetime import timedelta

from sqlmodel import Session, select

from app.admin import claim_legacy
from app.models import Group, Invite, MatchPlayer, Membership, Player, utc_now


def make_group(client, name="Our pool"):
    response = client.post("/api/groups", json={"name": name})
    assert response.status_code == 201, response.text
    group = response.json()
    client.headers["X-Group-ID"] = str(group["id"])
    return group


def make_invite(client, **kwargs):
    response = client.post("/api/groups/invites", json=kwargs)
    assert response.status_code == 201, response.text
    return response.json()


def join(client, code):
    response = client.post("/api/groups/join", json={"code": code})
    assert response.status_code == 200, response.text
    group = response.json()
    client.headers["X-Group-ID"] = str(group["id"])
    return group


def match_body(first, second):
    return {"orange_score": 10, "blue_score": 7, "players": [{"player_id": first, "side": "orange", "position": "solo"}, {"player_id": second, "side": "blue", "position": "solo"}]}


def test_create_group_profile_and_invite_flow(registered, db_engine):
    admin, _ = registered()
    group = make_group(admin)
    assert group["role"] == "admin" and group["player_id"]
    invite = make_invite(admin, max_uses=1)
    assert len(invite["code"]) >= 24
    assert invite["expires_at"].endswith("Z")
    assert "code" not in admin.get("/api/groups/invites").json()[0]
    with Session(db_engine) as session:
        assert session.get(Invite, invite["id"]).code_hash != invite["code"]
    member, user = registered("member@example.org", "Member")
    joined = join(member, invite["code"])
    assert joined["role"] == "member" and joined["id"] == group["id"]
    assert member.get("/api/players/me").json()["user_id"] == user["id"]
    assert member.get("/api/players/me").json()["created_at"].endswith("Z")
    assert join(member, invite["code"])["player_id"] == joined["player_id"]  # idempotent
    other, _ = registered("other@example.org")
    assert other.post("/api/groups/join", json={"code": invite["code"]}).status_code == 409


def test_group_isolation_for_all_resources_and_player_ids(registered):
    alice, _ = registered("alice@example.org", "Alice")
    bob, _ = registered("bob@example.org", "Bob")
    a, b = make_group(alice, "A"), make_group(bob, "B")
    own = alice.post("/api/players", json={"name": "Teammate"}).json()
    foreign = bob.post("/api/players", json={"name": "Teammate"}).json()  # Same names allowed across groups.
    created = alice.post("/api/matches", json=match_body(a["player_id"], own["id"]))
    assert created.status_code == 201 and created.json()["played_at"].endswith("Z")
    foreign_invite = make_invite(bob)
    assert alice.patch(f"/api/players/{foreign['id']}", json={"name": "Stolen"}).status_code == 404
    assert alice.delete(f"/api/players/{foreign['id']}").status_code == 404
    assert alice.delete(f"/api/groups/invites/{foreign_invite['id']}").status_code == 404
    assert alice.post("/api/matches", json=match_body(a["player_id"], foreign["id"])).status_code == 422
    assert bob.get("/api/matches").json() == []
    assert bob.get("/api/stats").json()["global"]["total_matches"] == 0
    assert bob.delete(f"/api/matches/{created.json()['id']}").status_code == 404
    assert all(p["group_id"] == a["id"] for p in alice.get("/api/players").json())
    assert [g["id"] for g in alice.get("/api/groups").json()] == [a["id"]]
    alice.headers["X-Group-ID"] = str(b["id"])
    for path in ("/api/players", "/api/matches", "/api/stats", "/api/groups/current", "/api/groups/members", "/api/groups/invites"):
        assert alice.get(path).status_code == 404
    assert alice.post("/api/players", json={"name": "Foreign"}).status_code == 404


def test_member_rights_and_last_admin_preserved(registered):
    admin, administrator = registered()
    group = make_group(admin)
    member, user = registered("member@example.org", "Member")
    join(member, make_invite(admin)["code"])
    assert member.get("/api/groups/members").status_code == 403
    assert member.post("/api/players", json={"name": "New"}).status_code == 403
    assert member.post("/api/groups/invites", json={}).status_code == 403
    assert member.patch("/api/groups/current", json={"name": "Renamed"}).status_code == 403
    assert member.patch("/api/players/me", json={"name": "Own profile"}).status_code == 200
    assert admin.patch(f"/api/groups/members/{administrator['id']}", json={"role": "member"}).status_code == 409
    assert admin.delete(f"/api/groups/members/{administrator['id']}").status_code == 409
    assert admin.patch(f"/api/groups/members/{user['id']}", json={"role": "admin"}).status_code == 200
    assert admin.patch(f"/api/groups/members/{administrator['id']}", json={"role": "member"}).status_code == 200
    assert admin.post("/api/players", json={"name": "Now disallowed"}).status_code == 403
    assert member.delete(f"/api/groups/members/{administrator['id']}").status_code == 204
    assert admin.get("/api/groups").json() == []
    assert admin.get("/api/players").status_code == 404
    assert admin.get("/api/auth/me").status_code == 200  # Group removal does not delete account.
    assert member.get("/api/groups/current").json()["id"] == group["id"]


def test_invite_revoke_expiration_and_unknown_code(registered, db_engine):
    admin, _ = registered()
    make_group(admin)
    member, _ = registered("member@example.org")
    revoked = make_invite(admin)
    assert admin.delete(f"/api/groups/invites/{revoked['id']}").status_code == 204
    assert member.post("/api/groups/join", json={"code": revoked["code"]}).status_code == 404
    expired = make_invite(admin)
    with Session(db_engine) as session:
        invite = session.get(Invite, expired["id"])
        invite.expires_at = utc_now() - timedelta(seconds=1)
        session.add(invite)
        session.commit()
    assert member.post("/api/groups/join", json={"code": expired["code"]}).status_code == 404
    assert member.post("/api/groups/join", json={"code": "does-not-exist"}).status_code == 404


def test_deactivation_keeps_history_and_blocks_new_matches(registered, db_engine):
    admin, _ = registered()
    group = make_group(admin)
    second = admin.post("/api/players", json={"name": "Second"}).json()
    match = admin.post("/api/matches", json=match_body(group["player_id"], second["id"]))
    assert match.status_code == 201
    assert admin.delete(f"/api/players/{second['id']}").status_code == 204
    assert all(p["id"] != second["id"] for p in admin.get("/api/players").json())
    assert any(p["id"] == second["id"] and not p["is_active"] for p in admin.get("/api/players?include_inactive=true").json())
    assert len(admin.get("/api/matches").json()) == 1
    assert admin.get("/api/stats").json()["global"]["total_matches"] == 1
    assert admin.post("/api/matches", json=match_body(group["player_id"], second["id"])).status_code == 422
    with Session(db_engine) as session:
        assert len(session.exec(select(MatchPlayer)).all()) == 2
        assert session.get(Player, second["id"]) is not None
    assert admin.patch(f"/api/players/{second['id']}", json={"is_active": True}).status_code == 200
    assert admin.post("/api/matches", json=match_body(group["player_id"], second["id"])).status_code == 201


def test_profile_binding_by_user_id_preserves_historic_player(registered):
    admin, administrator = registered()
    group = make_group(admin)
    historical = admin.post("/api/players", json={"name": "Historic nickname"}).json()
    response = admin.patch(f"/api/players/{historical['id']}", json={"user_id": administrator["id"]})
    assert response.status_code == 200
    assert admin.get("/api/players/me").json()["id"] == historical["id"]
    assert admin.get("/api/groups/current").json()["player_id"] == historical["id"]
    old = next(p for p in admin.get("/api/players?include_inactive=true").json() if p["id"] == group["player_id"])
    assert old["user_id"] is None and not old["is_active"]
    other, other_user = registered("other@example.org")
    make_group(other)
    assert admin.patch(f"/api/players/{historical['id']}", json={"user_id": other_user["id"]}).status_code == 422
    second = admin.post("/api/players", json={"name": "Second"}).json()
    assert admin.post("/api/matches", json=match_body(historical["id"], second["id"])).status_code == 201
    assert admin.patch(f"/api/players/{second['id']}", json={"user_id": administrator["id"]}).status_code == 409
    assert admin.get("/api/players/me").json()["id"] == historical["id"]


def test_legacy_group_requires_explicit_operator_claim(registered, db_engine):
    with Session(db_engine) as session:
        legacy = Group(name="Legacy", is_legacy=True)
        session.add(legacy)
        session.commit()
        legacy_id = legacy.id
        session.add(Player(name="Office player", group_id=legacy_id))
        session.commit()
    client, user = registered()
    assert client.get("/api/groups").json() == []
    client.headers["X-Group-ID"] = str(legacy_id)
    assert client.get("/api/players").status_code == 404
    with Session(db_engine) as session:
        assert claim_legacy(session, user["email"]) == legacy_id
        assert session.get(Membership, (legacy_id, user["id"])).role == "admin"
    assert client.get("/api/groups/current").json()["role"] == "admin"
    assert any(p["name"] == "Office player" for p in client.get("/api/players").json())


def test_score_bounds_and_admin_only_match_corrections(registered):
    admin, _ = registered()
    group = make_group(admin)
    member, _ = registered("member@example.org")
    joined = join(member, make_invite(admin)["code"])
    body = match_body(group["player_id"], joined["player_id"])
    for score in (-1, 11):
        assert member.post("/api/matches", json={**body, "blue_score": score}).status_code == 422
    assert member.post("/api/matches", json={**body, "blue_score": 10}).status_code == 422
    match = member.post("/api/matches", json=body)
    assert match.status_code == 201
    assert member.delete(f"/api/matches/{match.json()['id']}").status_code == 403
    assert admin.delete(f"/api/matches/{match.json()['id']}").status_code == 204


def test_requires_explicit_valid_group_selection(registered):
    client, _ = registered()
    for value in ("", "0", "-1", "text"):
        assert client.get("/api/players", headers={"X-Group-ID": value}).status_code == 400


def test_historical_names_read_without_new_input_limits(registered, db_engine):
    admin, _ = registered()
    group = make_group(admin)
    historical_name = "Historical name before limits " * 4
    with Session(db_engine) as session:
        session.add(Player(name=historical_name, group_id=group["id"]))
        session.commit()
    assert any(player["name"] == historical_name for player in admin.get("/api/players").json())
    assert admin.post("/api/players", json={"name": historical_name}).status_code == 422
    assert admin.post("/api/players", json={"name": " "}).status_code == 422
