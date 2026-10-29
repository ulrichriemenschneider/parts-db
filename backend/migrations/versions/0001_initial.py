"""Initial inventory schema, frozen independently of application models."""
from alembic import op
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = [
'''CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(100) NOT NULL UNIQUE, password_hash TEXT NOT NULL)''',
'''CREATE TABLE session (id VARCHAR(64) PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES user(id), csrf VARCHAR(64) NOT NULL, expires FLOAT NOT NULL, import_digest VARCHAR(64), import_state VARCHAR(64))''',
'''CREATE TABLE attempt (id INTEGER PRIMARY KEY, address VARCHAR(100) NOT NULL, at FLOAT NOT NULL)''',
'''CREATE INDEX ix_attempt_address ON attempt (address)''',
'''CREATE TABLE category (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL UNIQUE, fields JSON NOT NULL)''',
'''CREATE TABLE location (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL UNIQUE, parent_id INTEGER REFERENCES location(id))''',
'''CREATE TABLE supplier (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL UNIQUE)''',
'''CREATE TABLE part (id INTEGER PRIMARY KEY, name VARCHAR(300) NOT NULL, category_id INTEGER NOT NULL REFERENCES category(id), manufacturer VARCHAR(200) NOT NULL, mpn VARCHAR(200) NOT NULL, package VARCHAR(200) NOT NULL, description TEXT NOT NULL, notes TEXT NOT NULL, attributes JSON NOT NULL)''',
'''CREATE TABLE offer (id INTEGER PRIMARY KEY, part_id INTEGER NOT NULL REFERENCES part(id) ON DELETE CASCADE, supplier_id INTEGER NOT NULL REFERENCES supplier(id), article_number VARCHAR(200) NOT NULL, product_url TEXT NOT NULL, datasheet_url TEXT NOT NULL)''',
'''CREATE TABLE stock (id INTEGER PRIMARY KEY, part_id INTEGER NOT NULL REFERENCES part(id) ON DELETE CASCADE, location_id INTEGER NOT NULL REFERENCES location(id), quantity INTEGER NOT NULL CHECK (quantity >= 0), UNIQUE (part_id, location_id))'''
]
def upgrade():
    for statement in SCHEMA:
        op.execute(statement)
    for statement in ['INSERT INTO category (name, fields) VALUES (\'Widerstände\', \'[{"name": "Widerstand", "type": "number", "unit": "Ω"}, {"name": "Toleranz", "type": "number", "unit": "%"}]\')', 'INSERT INTO category (name, fields) VALUES (\'Kondensatoren\', \'[{"name": "Kapazität", "type": "number", "unit": "µF"}, {"name": "Spannungsfestigkeit", "type": "number", "unit": "V"}]\')', "INSERT INTO category (name, fields) VALUES ('Dioden', '[]')", "INSERT INTO category (name, fields) VALUES ('Transistoren', '[]')", "INSERT INTO category (name, fields) VALUES ('ICs', '[]')", "INSERT INTO category (name, fields) VALUES ('Module / Arduino', '[]')", "INSERT INTO category (name, fields) VALUES ('Sonstiges', '[]')"]:
        op.execute(statement)
def downgrade():
    for name in ('stock','offer','part','supplier','location','category','attempt','session','user'):
        op.execute('DROP TABLE '+name)
