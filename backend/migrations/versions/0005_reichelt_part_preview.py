"""Stage reviewable Reichelt creation separately from project completion."""
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE session ADD COLUMN reichelt_preview JSON')


def downgrade():
    op.execute('ALTER TABLE session DROP COLUMN reichelt_preview')
