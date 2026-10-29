"""Reichelt project demands, staged previews and idempotent goods receipts."""
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE session ADD COLUMN demand_preview JSON')
    op.execute('''CREATE TABLE demand_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(200) NOT NULL,
        source_filename VARCHAR(255) NOT NULL, source_digest VARCHAR(64) NOT NULL,
        imported_at FLOAT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1))''')
    op.execute('''CREATE TABLE demand_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT, list_id INTEGER NOT NULL REFERENCES demand_list(id) ON DELETE CASCADE,
        part_id INTEGER NOT NULL REFERENCES part(id), article_number VARCHAR(200) NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0), received INTEGER NOT NULL DEFAULT 0
        CHECK (received >= 0 AND received <= quantity), note TEXT NOT NULL,
        UNIQUE (list_id, article_number))''')
    op.execute('CREATE INDEX ix_demand_item_list_id ON demand_item(list_id)')
    op.execute('''CREATE TABLE goods_receipt (
        id VARCHAR(64) PRIMARY KEY, list_id INTEGER NOT NULL REFERENCES demand_list(id) ON DELETE CASCADE,
        payload_digest VARCHAR(64) NOT NULL, created_at FLOAT NOT NULL, items JSON NOT NULL)''')


def downgrade():
    for name in ('goods_receipt', 'demand_item', 'demand_list'):
        op.execute('DROP TABLE '+name)
    op.execute('ALTER TABLE session DROP COLUMN demand_preview')
