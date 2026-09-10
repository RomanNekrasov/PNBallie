"""Durable avatar jobs and private PNG images.

Revision ID: 20260909_avatars
Revises: 20260909_groups
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

revision = "20260909_avatars"
down_revision = "20260909_groups"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("avatar_job",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("active_player_id", sa.Integer(), nullable=True),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cloud_consent", sa.Boolean(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("source_png", sa.LargeBinary(), nullable=True),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_token", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("leased_until", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["player.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("active_player_id"),
    )
    for field in ["group_id", "player_id", "user_id", "status", "available_at", "leased_until"]:
        op.create_index(f"ix_avatar_job_{field}", "avatar_job", [field])
    op.create_table("player_avatar",
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("version", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("png", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["player.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.PrimaryKeyConstraint("player_id"),
    )
    op.create_index("ix_player_avatar_group_id", "player_avatar", ["group_id"])


def downgrade():
    op.drop_table("player_avatar")
    op.drop_table("avatar_job")
