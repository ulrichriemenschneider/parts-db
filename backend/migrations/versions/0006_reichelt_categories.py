"""Replace legacy categories with the verified, frozen Reichelt taxonomy."""
import json
from pathlib import Path
import secrets

from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

SNAPSHOT = Path(__file__).resolve().parents[2]/'data/reichelt_categories_20261029.json'
LEGACY = {'Widerstände':3059, 'Kondensatoren':3140, 'Dioden':2985,
          'Transistoren':2878, 'ICs':2906, 'Module / Arduino':8241, 'Sonstiges':2875}


def upgrade():
    connection = op.get_bind()
    snapshot = json.loads(SNAPSHOT.read_text())
    nodes = {node['id']:node for node in snapshot['categories']}
    if len(nodes) != snapshot['category_count'] or snapshot['unresolved_urls']:
        raise ValueError('Unvollständiger Reichelt-Kategorienstand.')
    if any(len(node['path']) > 200 for node in nodes.values()):
        raise ValueError('Kategoriepfad überschreitet das CSV-Textlimit.')
    old = {row['id']:dict(row) for row in connection.execute(sa.text('SELECT * FROM category')).mappings()}
    for row in old.values():
        row['fields'] = json.loads(row['fields'])
    parts = [dict(row) for row in connection.execute(sa.text('SELECT id,category_id,attributes FROM part')).mappings()]
    for part in parts:
        part['attributes'] = json.loads(part['attributes'])
    cache = {row['article_number']:json.loads(row['data']) for row in connection.execute(sa.text('SELECT * FROM product_cache')).mappings()}
    supplier_ids = {row['id'] for row in connection.execute(sa.text('SELECT * FROM supplier')).mappings()
                    if ' '.join(row['name'].split()).upper() in ('REICHELT','REICHELT ELEKTRONIK')}
    offers = {}
    for row in connection.execute(sa.text('SELECT * FROM offer')).mappings():
        if row['supplier_id'] in supplier_ids:
            offers.setdefault(row['part_id'], []).append(' '.join(row['article_number'].split()).upper())
    paths = {node['path']:ident for ident,node in nodes.items()}
    fields = {}
    for ident,node in nodes.items():
        lineage, current = set(), ident
        while current:
            if current in lineage:
                raise ValueError('Kreis im Kategorienbaum.')
            lineage.add(current)
            current = nodes[current]['parent_id']
        fields[ident] = ([dict(name='Widerstand',type='number',unit='Ω'),dict(name='Toleranz',type='number',unit='%')]
                         if 3059 in lineage else
                         [dict(name='Kapazität',type='number',unit='µF'),dict(name='Spannungsfestigkeit',type='number',unit='V')]
                         if 3140 in lineage else [])

    def matching_category(data):
        for node in reversed(data.get('categoryNodes', [])):
            if isinstance(node,dict) and node.get('id') in nodes:
                return node['id']
        names = [name.strip() for name in data.get('categories', []) if isinstance(name,str) and name.strip() not in ('Startseite','Home')]
        for start in range(len(names)):
            if ' › '.join(names[start:]) in paths:
                return paths[' › '.join(names[start:])]
        return None

    merged = {}
    def merge_fields(target, source):
        key = (target,source['id'])
        if key in merged:
            return merged[key]
        by_name = {field['name']:field for field in fields[target]}
        names = {}
        for original in source['fields']:
            field = dict(original)
            if field['name'] in by_name and field != by_name[field['name']]:
                # Keep the original numerical value and unit together. Never
                # silently reinterpret a pre-existing custom kΩ field as Ω.
                field['name'] += f" [bisher: {source['name']}, {field['unit'] or field['type']}]"
                while field['name'] in by_name and field != by_name[field['name']]:
                    field['name'] += f" #{source['id']}"
            names[original['name']] = field['name']
            if field['name'] not in by_name:
                fields[target].append(field)
                by_name[field['name']] = field
        merged[key] = names
        return names

    for source in old.values():
        merge_fields(LEGACY.get(source['name'],2875),source)
    for part in parts:
        source = old[part['category_id']]
        matches = {matching_category(cache[article]) for article in offers.get(part['id'],[]) if article in cache}
        matches.discard(None)
        target = next(iter(matches)) if len(matches) == 1 else LEGACY.get(source['name'],2875)
        names = merge_fields(target,source)
        part['attributes'] = {names.get(name,name):value for name,value in part['attributes'].items()}
        part['target'] = target
    start_id = max(old,default=0)+1
    ids = {ident:start_id+offset for offset,ident in enumerate(sorted(nodes))}
    prefix = '__previous_categories_'+secrets.token_hex(8)+'_'
    for ident in old:
        connection.execute(sa.text('UPDATE category SET name=:name WHERE id=:id'),dict(id=ident,name=prefix+str(ident)))
    connection.execute(sa.text('INSERT INTO category (id,name,fields) VALUES (:id,:name,:fields)'),
                       [dict(id=ids[ident],name=node['path'],fields=json.dumps(fields[ident],ensure_ascii=False)) for ident,node in sorted(nodes.items())])
    op.execute('''CREATE TABLE category_node (
        category_id INTEGER PRIMARY KEY REFERENCES category(id) ON DELETE CASCADE,
        reichelt_id INTEGER NOT NULL UNIQUE, parent_id INTEGER REFERENCES category(id),
        label VARCHAR(300) NOT NULL, source_url TEXT NOT NULL)''')
    connection.execute(sa.text('INSERT INTO category_node VALUES (:category_id,:reichelt_id,:parent_id,:label,:source_url)'),
                       [dict(category_id=ids[ident],reichelt_id=ident,parent_id=ids.get(node['parent_id']),label=node['name'],source_url=node['url'])
                        for ident,node in sorted(nodes.items())])
    for part in parts:
        connection.execute(sa.text('UPDATE part SET category_id=:category_id,attributes=:attributes WHERE id=:id'),
                           dict(id=part['id'],category_id=ids[part['target']],attributes=json.dumps(part['attributes'],ensure_ascii=False)))
    if old:
        connection.execute(sa.text('DELETE FROM category WHERE id IN ('+','.join(str(ident) for ident in old)+')'))
    connection.execute(sa.text('UPDATE session SET import_digest=NULL,import_state=NULL,demand_preview=NULL,enrichment_preview=NULL,reichelt_preview=NULL'))


def downgrade():
    raise RuntimeError('Die Kategorienersetzung wird über das vollständige Datenbankbackup zurückgenommen; alte Zuordnungen nicht erraten.')
