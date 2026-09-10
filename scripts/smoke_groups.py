"""End-to-end API smoke for a disposable local/CI stack; creates synthetic data.

python scripts/smoke_groups.py http://localhost:8080
The optional second argument overrides Origin for a direct backend check.
"""

import json
import secrets
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


class Client:
    def __init__(self, base, origin):
        self.base, self.origin = base, origin
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf = None
        self.group = None

    def call(self, method, path, body=None, expected=200):
        headers = {"Origin": self.origin}
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        if self.group:
            headers["X-Group-ID"] = str(self.group)
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                          headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            payload = response.read()
            assert response.status == expected, f"{method} {path}: expected {expected}, got {response.status}"
            return json.loads(payload) if payload else None

    def register(self, name, run):
        result = self.call("POST", "/api/auth/register", {
            "email": f"{name}-{run}@example.test", "display_name": name,
            "password": secrets.token_urlsafe(24),
        }, expected=201)
        self.csrf = result["csrf_token"]
        return result["user"]["id"]


def main():
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8080"
    origin = sys.argv[2] if len(sys.argv) > 2 else base
    if not base.startswith(("http://localhost:", "http://127.0.0.1:")):
        raise SystemExit("Use only a disposable localhost stack; this smoke creates test accounts and scores.")
    run = secrets.token_hex(5)
    admin, member = Client(base, origin), Client(base, origin)
    admin.call("GET", "/api/players", expected=401)
    assert admin.call("GET", "/api/auth/providers")["local"]
    admin.register("Captain", run)
    member_id = member.register("Challenger", run)
    group = admin.call("POST", "/api/groups", {"name": "Smoke competition " + run}, expected=201)
    admin.group = group["id"]
    invite = admin.call("POST", "/api/groups/invites", {"max_uses": 1}, expected=201)
    joined = member.call("POST", "/api/groups/join", {"code": invite["code"]})
    member.group = joined["id"]
    member.call("GET", "/api/groups/members", expected=403)
    member.call("POST", "/api/players", {"name": "Forbidden"}, expected=403)
    player = member.call("GET", "/api/players/me")
    assert player["user_id"] == member_id
    match = member.call("POST", "/api/matches", {
        "orange_score": 10, "blue_score": 6,
        "players": [{"player_id": group["player_id"], "side": "orange", "position": "solo"},
                    {"player_id": player["id"], "side": "blue", "position": "solo"}],
    }, expected=201)
    assert match["played_at"].endswith("Z"), "API timestamps must specify UTC"
    stats = member.call("GET", "/api/stats?mode=1v1&period=50")
    assert stats["global"]["total_matches"] == 1
    assert stats["global"]["average_goal_difference"] == 4
    assert member.call("GET", "/api/stats?mode=2v2&period=all")["global"]["total_matches"] == 0
    private = admin.call("POST", "/api/groups", {"name": "Separate smoke group " + run}, expected=201)
    member.group = private["id"]
    for path in ("/api/players", "/api/matches", "/api/stats"):
        member.call("GET", path, expected=404)
    member.group = group["id"]
    admin.call("DELETE", f"/api/groups/members/{member_id}", expected=204)
    member.call("GET", "/api/stats", expected=404)
    assert admin.call("GET", "/api/stats")["global"]["total_matches"] == 1
    print("Smoke passed: signup, cookies/CSRF, group creation, invitations, player binding, score, filters and group isolation.")


if __name__ == "__main__":
    main()
