"""Persist daily project check dates across worker restarts."""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('revision_diaria', sa.Column('fecha', sa.Date(), primary_key=True))


def downgrade() -> None:
    op.drop_table('revision_diaria')
