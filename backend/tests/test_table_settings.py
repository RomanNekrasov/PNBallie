import pytest
from test_groups import join, make_group, make_invite, match_body

from app.table_settings import TableSettings


def test_table_settings_are_shared_persisted_and_do_not_change_matches(registered):
    admin, _ = registered()
    group = make_group(admin)
    assert group["table_settings"] == TableSettings().model_dump()
    member, _ = registered("member@example.org")
    joined = join(member, make_invite(admin)["code"])
    match = admin.post("/api/matches", json=match_body(group["player_id"], joined["player_id"])).json()
    settings = TableSettings(orange_color="red", blue_color="white", field_color="#123456", rim_color="#abcdef", score_position="own_goal").model_dump()
    response = admin.put("/api/groups/current/table", json=settings)
    assert response.status_code == 200, response.text
    assert response.json()["table_settings"] == settings
    assert member.get("/api/groups/current").json()["table_settings"] == settings
    assert member.get("/api/groups").json()[0]["table_settings"] == settings
    assert admin.get("/api/matches").json()[0] == match
    admin.patch("/api/groups/current", json={"name": "Renamed"})
    assert admin.get("/api/groups/current").json()["table_settings"] == settings
    assert admin.put("/api/groups/current/table", json=TableSettings().model_dump()).json()["table_settings"] == TableSettings().model_dump()


def test_only_group_admin_can_change_own_table(registered):
    admin, _ = registered()
    own = make_group(admin)
    member, _ = registered("member@example.org")
    join(member, make_invite(admin)["code"])
    assert member.put("/api/groups/current/table", json={"orange_color": "red"}).status_code == 403
    other, _ = registered("other@example.org")
    foreign = make_group(other)
    admin.put("/api/groups/current/table", json={"orange_color": "red"})
    assert other.get("/api/groups/current").json()["table_settings"] == TableSettings().model_dump()
    admin.headers["X-Group-ID"] = str(foreign["id"])
    assert admin.put("/api/groups/current/table", json={"orange_color": "green"}).status_code == 404
    admin.headers["X-Group-ID"] = str(own["id"])
    assert admin.get("/api/groups/current").json()["table_settings"]["orange_color"] == "red"


@pytest.mark.parametrize("payload", [
    {"orange_color": "blue"}, {"blue_color": "cyan"}, {"score_position": "left"},
    {"field_color": "red; background:url(evil)"}, {"rim_color": "#123"},
    {"field_color": None}, {"unknown": True},
])
def test_invalid_settings_are_rejected_without_overwriting(registered, payload):
    admin, _ = registered()
    make_group(admin)
    assert admin.put("/api/groups/current/table", json=payload).status_code == 422
    assert admin.get("/api/groups/current").json()["table_settings"] == TableSettings().model_dump()
