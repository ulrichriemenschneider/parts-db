"""Staged product updates and shared browser-fetch cache/limits."""
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE session ADD COLUMN enrichment_preview JSON')
    op.execute('''CREATE TABLE product_cache (article_number VARCHAR(200) PRIMARY KEY,
        fetched_at FLOAT NOT NULL, data JSON NOT NULL)''')
    op.execute('''CREATE TABLE product_fetch_state (id INTEGER PRIMARY KEY, lease VARCHAR(64) NOT NULL,
        lease_until FLOAT NOT NULL, last_started FLOAT NOT NULL, blocked_until FLOAT NOT NULL)''')
    op.execute("INSERT INTO product_fetch_state VALUES (1, '', 0, 0, 0)")


def downgrade():
    op.execute('DROP TABLE product_fetch_state')
    op.execute('DROP TABLE product_cache')
    op.execute('ALTER TABLE session DROP COLUMN enrichment_preview')
