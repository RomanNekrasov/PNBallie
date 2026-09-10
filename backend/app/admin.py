"""Operator-only recovery/bootstrap, run against the intended SQLite database.

uv run python -m app.admin claim-legacy --email admin@example.org
"""

import argparse

from sqlmodel import Session, select

from app.database import engine
from app.models import Group, Membership, User
from app.routers.groups import ensure_member_player


def claim_legacy(session: Session, email: str) -> int:
    user = session.exec(select(User).where(User.email == email.strip().lower())).first()
    if not user:
        raise ValueError("Register the administrator account first; no account exists for this e-mail")
    legacy = session.exec(select(Group).where(Group.is_legacy.is_(True))).first()
    if not legacy:
        raise ValueError("No legacy competition exists; run the database migrations first")
    existing = session.get(Membership, (legacy.id, user.id))
    if existing is None:
        existing = Membership(group_id=legacy.id, user_id=user.id, role="admin")
    existing.role = "admin"
    session.add(existing)
    ensure_member_player(session, legacy.id, user)
    session.commit()
    return legacy.id


def main() -> None:
    parser = argparse.ArgumentParser(description="PNBallie operator administration")
    commands = parser.add_subparsers(dest="command", required=True)
    claim = commands.add_parser("claim-legacy", help="Grant a registered account admin access to migrated history")
    claim.add_argument("--email", required=True, help="Exact e-mail of the account you verified out of band")
    args = parser.parse_args()
    with Session(engine) as session:
        try:
            group_id = claim_legacy(session, args.email)
        except ValueError as exc:
            parser.error(str(exc))
    print(f"Administrator access granted for legacy group {group_id}. Link the historic player in group administration.")


if __name__ == "__main__":
    main()
