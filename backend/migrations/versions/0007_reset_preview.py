"""Stage an explicit, state-bound inventory reset without changing categories."""
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE session ADD COLUMN reset_preview JSON')


def downgrade():
    op.execute('ALTER TABLE session DROP COLUMN reset_preview')
