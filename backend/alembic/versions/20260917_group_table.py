"""Store each group's table appearance without changing match sides."""
import sqlalchemy as sa

from alembic import op

revision = "20260917_table"
down_revision = "20260916_recorder"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("group") as batch:
        batch.add_column(sa.Column("table_settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade():
    with op.batch_alter_table("group") as batch:
        batch.drop_column("table_settings")
