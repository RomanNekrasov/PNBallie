"""Keep the original authenticated match recorder; historical origin is unknown."""

import sqlalchemy as sa

from alembic import op

revision = "20260916_recorder"
down_revision = "20260916_reset"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("match") as batch:
        batch.add_column(sa.Column("recorded_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("recorded_by_name", sa.String(80), nullable=True))
        batch.create_foreign_key("fk_match_recorder", "app_user", ["recorded_by_user_id"], ["id"], ondelete="SET NULL")


def downgrade():
    with op.batch_alter_table("match") as batch:
        batch.drop_constraint("fk_match_recorder", type_="foreignkey")
        batch.drop_column("recorded_by_name")
        batch.drop_column("recorded_by_user_id")
