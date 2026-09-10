"""Portable authentication and isolated groups; preserve existing competition.

Revision ID: 20260909_groups
Revises: 2895eb84caa9
"""

from datetime import datetime, timezone

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

revision = "20260909_groups"
down_revision = "2895eb84caa9"
branch_labels = None
depends_on = None

S = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    op.create_table("app_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", S(length=254), nullable=False),
        sa.Column("display_name", S(length=80), nullable=False),
        sa.Column("password_hash", S(), nullable=True),
        sa.Column("oidc_issuer", S(), nullable=True),
        sa.Column("oidc_subject", S(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_user_oidc"),
    )
    op.create_index("ix_app_user_email", "app_user", ["email"], unique=True)
    op.create_table("login_session",
        sa.Column("token_hash", S(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("csrf_token", S(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_login_session_user_id", "login_session", ["user_id"])
    op.create_table("auth_throttle",
        sa.Column("key", S(), primary_key=True),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_table("oidc_login",
        sa.Column("state_hash", S(), primary_key=True),
        sa.Column("nonce", S(), nullable=False),
        sa.Column("verifier", S(), nullable=False),
        sa.Column("next_path", S(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    group = op.create_table("group",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", S(length=80), nullable=False),
        sa.Column("is_legacy", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    # No membership is created: possession of an unverified e-mail must never
    # grant access to historical office results. Use the operator claim CLI.
    op.bulk_insert(group, [{"id": 1, "name": "Bestaande competitie", "is_legacy": True, "created_at": datetime.now(timezone.utc)}])
    op.create_table("membership",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group.id"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("role", S(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table("invite",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group.id"), nullable=False),
        sa.Column("code_hash", S(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses", sa.Integer(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_invite_group_id", "invite", ["group_id"])
    op.create_index("ix_invite_code_hash", "invite", ["code_hash"], unique=True)
    with op.batch_alter_table("player") as batch:
        batch.drop_index("ix_player_name")
        batch.alter_column("name", existing_type=S(), type_=S(length=80), existing_nullable=False)
        batch.add_column(sa.Column("group_id", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.create_foreign_key("fk_player_group", "group", ["group_id"], ["id"])
        batch.create_foreign_key("fk_player_user", "app_user", ["user_id"], ["id"])
        batch.create_index("ix_player_group_id", ["group_id"])
        batch.create_index("ix_player_user_id", ["user_id"])
        batch.create_unique_constraint("uq_player_group_name", ["group_id", "name"])
        batch.create_unique_constraint("uq_player_group_user", ["group_id", "user_id"])
    with op.batch_alter_table("player") as batch:
        batch.alter_column("group_id", server_default=None)
        batch.alter_column("is_active", server_default=None)
    with op.batch_alter_table("match") as batch:
        batch.add_column(sa.Column("group_id", sa.Integer(), nullable=False, server_default="1"))
        batch.create_foreign_key("fk_match_group", "group", ["group_id"], ["id"])
        batch.create_index("ix_match_group_id", ["group_id"])
    with op.batch_alter_table("match") as batch:
        batch.alter_column("group_id", server_default=None)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text('SELECT COUNT(*) FROM "group" WHERE is_legacy = 0')).scalar():
        raise RuntimeError("Refusing downgrade: new isolated groups exist. Restore a pre-migration backup instead.")
    with op.batch_alter_table("match") as batch:
        batch.drop_constraint("fk_match_group", type_="foreignkey")
        batch.drop_index("ix_match_group_id")
        batch.drop_column("group_id")
    with op.batch_alter_table("player") as batch:
        batch.drop_constraint("fk_player_group", type_="foreignkey")
        batch.drop_constraint("fk_player_user", type_="foreignkey")
        batch.drop_constraint("uq_player_group_name", type_="unique")
        batch.drop_constraint("uq_player_group_user", type_="unique")
        batch.drop_index("ix_player_group_id")
        batch.drop_index("ix_player_user_id")
        batch.drop_column("group_id")
        batch.drop_column("user_id")
        batch.drop_column("is_active")
        batch.alter_column("name", existing_type=S(length=80), type_=S(), existing_nullable=False)
        batch.create_index("ix_player_name", ["name"], unique=True)
    op.drop_table("invite")
    op.drop_table("membership")
    op.drop_table("group")
    op.drop_table("oidc_login")
    op.drop_table("auth_throttle")
    op.drop_table("login_session")
    op.drop_table("app_user")
