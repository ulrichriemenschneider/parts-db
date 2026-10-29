"""Project demand import and atomic, retry-safe receipts."""
import hashlib
import json
import re
import secrets
import time
from pathlib import PurePath

from flask import abort, g, jsonify, request
from sqlalchemy import select, update

from .models import db, User, Category, Supplier, Part, Offer, Stock, Location, DemandList, DemandItem, GoodsReceipt
from .reichelt import article_key, parse_list, lookup
from .product_fetch import available
from .curation import part_data, mark_reichelt, mark_manual
from .categories import default_category, resolve_category


def register_demands(app, integer, validate, row):
    def text(value, label, maximum=200):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f'{label}: Text mit 1 bis {maximum} Zeichen erforderlich.')
        return value.strip()

    def fingerprint():
        snapshot = {model.__tablename__: [row(obj) for obj in db.session.scalars(select(model).order_by(model.id))]
                    for model in (Category, Supplier, Part, Offer)}
        return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def suppliers():
        return [supplier for supplier in db.session.scalars(select(Supplier))
                if article_key(supplier.name) in ('REICHELT', 'REICHELT ELEKTRONIK')]

    def matching_part(article):
        supplier_ids = [supplier.id for supplier in suppliers()]
        matches = {offer.part_id for offer in db.session.scalars(select(Offer).where(Offer.supplier_id.in_(supplier_ids)))
                   if article_key(offer.article_number) == article_key(article)}
        if len(matches) > 1:
            raise ValueError(f'{article}: Mehrere Bauteile mit dieser Reichelt-Artikelnummer. Bitte Angebote zuerst bereinigen.')
        return db.session.get(Part, next(iter(matches))) if matches else None

    def list_data(demand, details=False):
        items = db.session.scalars(select(DemandItem).where(DemandItem.list_id == demand.id).order_by(DemandItem.id)).all()
        result = {**row(demand), 'positions': len(items), 'quantity': sum(item.quantity for item in items),
                  'received': sum(item.received for item in items)}
        if details:
            result['product_enrichment_available'] = available(app)
            result['items'] = [{**row(item), 'remaining': item.quantity-item.received,
                                'part': part_data(db.session.get(Part, item.part_id))} for item in items]
        return result

    def preview_data(preview):
        return {key: value for key, value in preview.items() if key not in ('state', 'created')}

    def require_preview(token):
        preview = g.auth.demand_preview
        if not isinstance(token, str) or not preview or not secrets.compare_digest(preview['token'], token):
            raise ValueError('Reichelt-Liste bitte zuerst erneut prüfen.')
        if preview['created'] < time.time()-1800:
            raise ValueError('Die Importvorschau ist abgelaufen. Bitte Datei erneut prüfen.')
        return preview

    def preview_import(payload, filename, name=None):
        parsed = parse_list(payload)
        # Serialize preview against inventory writes as well as other previews for this account.
        db.session.execute(update(User).values(username=User.username))
        filename = PurePath((filename or 'reichelt.csv').replace('\\', '/')).name[:255]
        name = text(name or PurePath(filename).stem, 'Projektname')
        digest = hashlib.sha256(payload).hexdigest()
        duplicate = db.session.scalar(select(DemandList).where(DemandList.name == name, DemandList.source_digest == digest))
        if duplicate:
            abort(409, 'Diese Datei wurde unter diesem Projektnamen bereits importiert. Bitte die vorhandene Liste öffnen oder einen anderen Namen verwenden.')
        default = default_category()
        items = []
        for index, source in enumerate(parsed):
            part = matching_part(source['article_number'])
            items.append({**source, 'index': index, 'part_id': part.id if part else None,
                          'name': part.name if part else source['article_number'],
                          'category_id': part.category_id if part else default.id if default else None,
                          'manufacturer': part.manufacturer if part else '', 'mpn': part.mpn if part else '',
                          'package': part.package if part else '', 'description': '', 'product_url': '',
                          'suggested_attributes': {}, 'enriched': False})
        preview = dict(format='reichelt', token=secrets.token_hex(32), name=name, source_filename=filename,
                       source_digest=digest, created=time.time(), state=fingerprint(), items=items,
                       enrichment_available=bool(app.config.get('REICHELT_API_KEY')))
        g.auth.demand_preview = preview
        db.session.commit()
        return jsonify(preview_data(preview))

    @app.get('/api/demands/import-options')
    def import_options():
        return jsonify(enrichment_available=bool(app.config.get('REICHELT_API_KEY')))

    @app.route('/api/demands/import', methods=['POST'])
    def import_list():
        if not request.is_json:
            upload = request.files.get('file')
            if not upload:
                raise ValueError('Reichelt-CSV-Datei fehlt.')
            return preview_import(upload.read(), upload.filename, request.form.get('project_name'))
        data = request.get_json()
        db.session.execute(update(User).values(username=User.username))
        db.session.refresh(g.auth)
        preview = require_preview(data.get('token'))
        if preview['state'] != fingerprint():
            abort(409, 'Bauteile oder Stammdaten wurden seit der Vorschau verändert. Bitte Datei erneut prüfen.')
        name = text(data.get('name', preview['name']), 'Projektname')
        if db.session.scalar(select(DemandList.id).where(DemandList.name == name, DemandList.source_digest == preview['source_digest'])):
            abort(409, 'Diese Datei wurde unter diesem Projektnamen bereits importiert.')
        edits = data.get('items', [])
        if not isinstance(edits, list) or len(edits) != len(preview['items']):
            raise ValueError('Alle Positionen der Vorschau sind erforderlich.')
        by_index = {}
        for edit in edits:
            if not isinstance(edit, dict) or set(edit) != {'index', 'name', 'category_id'}:
                raise ValueError('Ungültige Positionsdaten.')
            index = integer(edit['index'], 'Position', 0)
            if index in by_index:
                raise ValueError('Doppelte Position.')
            by_index[index] = edit
        if set(by_index) != set(range(len(preview['items']))):
            raise ValueError('Positionen stimmen nicht mit der Vorschau überein.')
        known_suppliers = suppliers()
        supplier = known_suppliers[0] if known_suppliers else Supplier(name='Reichelt')
        if not known_suppliers:
            db.session.add(supplier)
            db.session.flush()
        demand = DemandList(name=name, source_filename=preview['source_filename'], source_digest=preview['source_digest'],
                            imported_at=time.time(), version=1)
        db.session.add(demand)
        db.session.flush()
        for item in preview['items']:
            part = db.session.get(Part, item['part_id']) if item['part_id'] else None
            if not part:
                edit = by_index[item['index']]
                category_id = integer(edit['category_id'], 'Kategorie')
                category = db.get_or_404(Category, category_id)
                units = {'Widerstand': 'Ω', 'Toleranz': '%', 'Kapazität': 'µF', 'Spannungsfestigkeit': 'V'}
                attrs = {field['name']: item['suggested_attributes'][field['name']] for field in category.fields
                         if field['type'] == 'number' and field['name'] in item['suggested_attributes']
                         and field['unit'] == units.get(field['name'])}
                part = Part(**validate(Part, dict(name=text(edit['name'], 'Bezeichnung', 300), category_id=category_id,
                            manufacturer=item['manufacturer'], mpn=item['mpn'], package=item['package'],
                            description=item['description'], attributes=attrs)))
                db.session.add(part)
                db.session.flush()
                if item.get('enriched'):
                    mark_reichelt(part)
                if edit['name'].strip() != item['name'] or category_id != item['category_id']:
                    mark_manual(part)
                db.session.add(Offer(**validate(Offer, dict(part_id=part.id, supplier_id=supplier.id,
                                                           article_number=item['article_number'], product_url=item['product_url']))))
            db.session.add(DemandItem(list_id=demand.id, part_id=part.id, article_number=item['article_number'],
                                     quantity=item['quantity'], received=0, note=item['note']))
        g.auth.demand_preview = None
        db.session.commit()
        return jsonify(list_data(demand, True)), 201

    @app.post('/api/demands/import/enrich')
    def enrich():
        data = request.get_json()
        preview = require_preview(data.get('token'))
        index = integer(data.get('index'), 'Position', 0)
        if index >= len(preview['items']):
            raise ValueError('Unbekannte Position.')
        if preview['items'][index]['part_id']:
            raise ValueError('Vorhandene Bauteile bleiben unverändert und können in der Bauteilverwaltung bearbeitet werden.')
        key = app.config.get('REICHELT_API_KEY')
        if not key:
            raise ValueError('Optionale Produktdatenabfrage ist nicht eingerichtet. Der Import funktioniert ohne sie.')
        article = preview['items'][index]['article_number']
        db.session.rollback()  # No database writer lock is held during a network request.
        suggestion = lookup(article, key)
        db.session.execute(update(User).values(username=User.username))
        db.session.refresh(g.auth)
        preview = require_preview(data.get('token'))
        category = resolve_category(suggestion)
        items = [dict(item) for item in preview['items']]
        items[index].update(suggestion, enriched=True)
        if category:
            items[index]['category_id'] = category.id
        g.auth.demand_preview = {**preview, 'items': items}
        db.session.commit()
        return jsonify(preview_data(g.auth.demand_preview))

    @app.get('/api/demands')
    def lists():
        return jsonify([list_data(demand) for demand in db.session.scalars(select(DemandList).order_by(DemandList.id.desc()))])

    @app.route('/api/demands/<int:ident>', methods=['GET', 'PUT', 'DELETE'])
    def demand_detail(ident):
        if request.method != 'GET':
            db.session.execute(update(DemandList).where(DemandList.id == ident).values(version=DemandList.version))
        demand = db.get_or_404(DemandList, ident)
        if request.method == 'DELETE':
            if request.args.get('confirm') != 'yes':
                raise ValueError('Löschen der Bedarfsliste bitte bestätigen. Bereits gebuchte Bestände bleiben erhalten.')
            db.session.delete(demand)
            db.session.commit()
            return jsonify(ok=True)
        if request.method == 'PUT':
            demand.name = text(request.get_json().get('name'), 'Projektname')
            demand.version += 1
            db.session.commit()
        return jsonify(list_data(demand, True))

    @app.post('/api/demands/<int:ident>/receive')
    def receive(ident):
        data = request.get_json()
        token = data.get('request_id')
        if not isinstance(token, str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,64}', token):
            raise ValueError('Ungültige Buchungskennung. Bitte Liste erneut öffnen.')
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        db.session.execute(update(DemandList).where(DemandList.id == ident).values(version=DemandList.version))
        demand = db.get_or_404(DemandList, ident)
        previous = db.session.get(GoodsReceipt, token)
        if previous:
            if previous.list_id != ident or previous.payload_digest != digest:
                abort(409, 'Diese Buchungskennung wurde bereits für andere Angaben verwendet. Bitte Liste neu laden.')
            return jsonify(list=list_data(demand, True), repeated=True)
        if integer(data.get('version'), 'Listenversion') != demand.version:
            abort(409, 'Die Bedarfsliste wurde inzwischen verändert. Bitte neu laden und offene Mengen prüfen.')
        selected = data.get('items')
        if not isinstance(selected, list) or not selected or len(selected) > 1000:
            raise ValueError('Mindestens eine Position für den Wareneingang auswählen.')
        seen, receipt_items = set(), []
        for entry in selected:
            if not isinstance(entry, dict) or set(entry) != {'item_id', 'quantity', 'location_id'}:
                raise ValueError('Ungültige Wareneingangsposition.')
            item_id = integer(entry['item_id'], 'Position')
            if item_id in seen:
                raise ValueError('Eine Position darf je Buchung nur einmal vorkommen.')
            seen.add(item_id)
            item = db.get_or_404(DemandItem, item_id)
            if item.list_id != demand.id:
                raise ValueError('Position gehört nicht zu dieser Bedarfsliste.')
            quantity = integer(entry['quantity'], 'Eingangsmenge')
            if quantity > item.quantity-item.received:
                raise ValueError(f'{item.article_number}: Eingangsmenge überschreitet den offenen Bedarf ({item.quantity-item.received}).')
            location_id = integer(entry['location_id'], 'Lagerplatz')
            db.get_or_404(Location, location_id)
            stock = db.session.scalar(select(Stock).where(Stock.part_id == item.part_id, Stock.location_id == location_id))
            if not stock:
                stock = Stock(part_id=item.part_id, location_id=location_id, quantity=0)
                db.session.add(stock)
            stock.quantity = integer(stock.quantity+quantity, 'Resultierender Bestand', 0)
            item.received += quantity
            receipt_items.append(dict(item_id=item_id, part_id=item.part_id, location_id=location_id, quantity=quantity))
        demand.version += 1
        db.session.add(GoodsReceipt(id=token, list_id=ident, payload_digest=digest, created_at=time.time(), items=receipt_items))
        db.session.commit()
        return jsonify(list=list_data(demand, True), repeated=False)

    from .enrichment import register_enrichment
    register_enrichment(app, integer, validate, row, fingerprint, list_data)
    return preview_import
