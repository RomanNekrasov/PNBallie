from sqlmodel import Session

from app.models import Player
from tests.test_groups import join, make_group, make_invite, match_body


def setup_match(registered):
    admin, _ = registered()
    group = make_group(admin)
    second = admin.post('/api/players', json={'name':'Second'}).json()['id']
    body = match_body(group['player_id'], second)
    match = admin.post('/api/matches', json=body).json()
    return admin, group, match


def update_body(match, **changes):
    return {**match, 'expected':match, **changes}


def test_admin_edit_recalculates_history_and_preserves_utc(registered):
    admin, _, match = setup_match(registered)
    path = f"/api/matches/{match['id']}"
    result = admin.put(path, json=update_body(match, orange_score=4, blue_score=10, played_at='2026-09-10T14:30:00+02:00'))
    assert result.status_code == 200, result.text
    edited = result.json()
    assert edited['played_at'] == '2026-09-10T12:30:00Z'
    assert edited['players'] == match['players']
    stats = admin.get('/api/stats').json()
    assert stats['global']['total_matches'] == 1
    assert stats['recent_matches'][0]['blue_score'] == 10
    assert admin.put(path, json=update_body(match)).status_code == 409
    assert admin.request('DELETE', path, json=match).status_code == 409
    assert admin.request('DELETE', path, json=edited).status_code == 204
    assert admin.get('/api/stats').json()['global']['total_matches'] == 0


def test_member_foreign_group_and_csrf_denied(registered):
    admin, _, match = setup_match(registered)
    member, _ = registered('member@example.org')
    join(member, make_invite(admin)['code'])
    foreign, _ = registered('foreign@example.org')
    make_group(foreign)
    path = f"/api/matches/{match['id']}"
    assert member.put(path, json=update_body(match)).status_code == 403
    assert member.request('DELETE', path, json=match).status_code == 403
    assert foreign.put(path, json=update_body(match)).status_code == 404
    assert foreign.request('DELETE', path, json=match).status_code == 404
    assert admin.put(path, json=update_body(match), headers={'X-CSRF-Token':''}).status_code == 403
    assert admin.request('DELETE', path, json=match, headers={'X-CSRF-Token':''}).status_code == 403


def test_validation_is_atomic_and_inactive_participants_can_be_retained(registered, db_engine):
    admin, _, match = setup_match(registered)
    path = f"/api/matches/{match['id']}"
    for changes in ({'orange_score':7}, {'played_at':'2026-09-10T12:00:00'}, {'players':[match['players'][0]]}, {'players':[match['players'][0],match['players'][0]]}):
        assert admin.put(path, json=update_body(match, **changes)).status_code == 422
        assert admin.get('/api/matches').json()[0] == match
    with Session(db_engine) as session:
        player = session.get(Player, match['players'][1]['player_id'])
        player.is_active=False
        session.add(player)
        session.commit()
    assert admin.put(path, json=update_body(match, blue_score=3)).status_code == 200
    assert admin.post('/api/matches', json=match).status_code == 422


def test_formations_and_pagination(registered):
    admin, group, match = setup_match(registered)
    extra = [admin.post('/api/players', json={'name':name}).json()['id'] for name in ['Third','Fourth']]
    slots=[{'player_id':pid,'side':side,'position':pos} for pid,side,pos in [(group['player_id'],'orange','voor'),(extra[0],'orange','achter'),(match['players'][1]['player_id'],'blue','voor'),(extra[1],'blue','achter')]]
    result=admin.put(f"/api/matches/{match['id']}", json=update_body(match, players=slots))
    assert result.status_code==200 and len(result.json()['players'])==4
    admin.post('/api/matches', json=match)
    first=admin.get('/api/matches?limit=1&offset=0').json()
    second=admin.get('/api/matches?limit=1&offset=1').json()
    assert len(first)==len(second)==1 and first[0]['id'] != second[0]['id']
    assert admin.get('/api/matches?limit=101').status_code==422
    assert admin.get('/api/matches?offset=-1').status_code==422
