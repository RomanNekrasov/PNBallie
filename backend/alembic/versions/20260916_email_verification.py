"""Email ownership proofs; existing accounts require explicit verification."""

import sqlalchemy as sa

from alembic import op

revision = "20260916_email"
down_revision = "20260910_telemetry"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("app_user", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    op.create_table("email_verification",
                    sa.Column("next_path", sa.String(500), nullable=False),
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), primary_key=True),
                    sa.Column("token_hash", sa.String(), nullable=False),
                    sa.Column("email", sa.String(254), nullable=False),
                    sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_email_verification_token_hash", "email_verification", ["token_hash"], unique=True)


def downgrade():
    op.drop_table("email_verification")
    with op.batch_alter_table("app_user") as batch:
        batch.drop_column("email_verified_at")
