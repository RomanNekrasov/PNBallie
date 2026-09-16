"""Hashed, single-use password recovery challenges."""

import sqlalchemy as sa

from alembic import op

revision = "20260916_reset"
down_revision = "20260916_email"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("password_reset",
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), primary_key=True),
                    sa.Column("token_hash", sa.String(), nullable=False),
                    sa.Column("email", sa.String(254), nullable=False),
                    sa.Column("password_fingerprint", sa.String(), nullable=False),
                    sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_password_reset_token_hash", "password_reset", ["token_hash"], unique=True)


def downgrade():
    op.drop_table("password_reset")
