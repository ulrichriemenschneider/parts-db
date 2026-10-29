"""Persist product-data provenance and explicit manual review state."""
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE part_curation (
        part_id INTEGER PRIMARY KEY REFERENCES part(id) ON DELETE CASCADE,
        reichelt_at FLOAT, manual_status VARCHAR(12) NOT NULL DEFAULT 'none'
        CHECK (manual_status IN ('none', 'partial', 'complete')))''')


def downgrade():
    op.execute('DROP TABLE part_curation')
