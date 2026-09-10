"""Preserve safe W3C trace context through the durable avatar queue.

Revision ID: 20260910_telemetry
Revises: 20260909_avatars
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

revision = "20260910_telemetry"
down_revision = "20260909_avatars"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("avatar_job") as batch:
        batch.add_column(sa.Column("traceparent", sqlmodel.sql.sqltypes.AutoString(length=55), nullable=True))


def downgrade():
    with op.batch_alter_table("avatar_job") as batch:
        batch.drop_column("traceparent")
