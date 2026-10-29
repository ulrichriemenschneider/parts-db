"""Create inventory parts from a reviewed, server-staged Reichelt product."""
import secrets
import time

from flask import abort, g, jsonify, request
from sqlalchemy import select, update

from .curation import part_data, mark_manual, mark_reichelt
from .models import db, User, Session, Category, Supplier, Part, Offer
from .product_fetch import get_product
from .reichelt import article_key, ATTRIBUTE_SPECS
from .categories import resolve_category


def register_part_import(app, validate):
    editable = {'name', 'manufacturer', 'mpn', 'package', 'description', 'notes', 'attributes'}

    def reichelt_suppliers():
        return [supplier for supplier in db.session.scalars(select(Supplier).order_by(Supplier.id))
                if article_key(supplier.name) in ('REICHELT', 'REICHELT ELEKTRONIK')]

    def existing_part(article):
        ids = [supplier.id for supplier in reichelt_suppliers()]
        matches = {offer.part_id for offer in db.session.scalars(select(Offer).where(Offer.supplier_id.in_(ids)))
                   if article_key(offer.article_number) == article_key(article)}
        if len(matches) > 1:
            raise ValueError('Mehrere Bauteile mit dieser Reichelt-Artikelnummer. Bitte Lieferantenangebote zuerst bereinigen.')
        return db.session.get(Part, next(iter(matches))) if matches else None

    @app.post('/api/parts/reichelt/preview')
    def preview_reichelt_part():
        identifier = request.get_json().get('identifier')
        if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 200:
            raise ValueError('Artikelnummer oder Herstellerteilenummer mit 1 bis 200 Zeichen erforderlich.')
        session_id = g.auth.id
        # The network request must not hold a database transaction or writer lock.
        db.session.rollback()
        product = get_product(app, identifier, allow_mpn=True)
        db.session.execute(update(User).values(username=User.username))
        db.session.expire_all()
        session = db.session.get(Session, session_id, populate_existing=True)
        if not session or session.expires <= time.time():
            abort(401, 'Bitte neu anmelden.')
        g.auth = session
        suggestion, article = product['suggestion'], product['article_number']
        category = resolve_category(suggestion)
        if not category:
            raise ValueError('Reichelt-Kategorien fehlen. Bitte Datenbankmigration ausführen.')
        fields = [dict(field) for field in category.fields]
        by_name = {field['name']: field for field in fields}
        attributes, warnings = {}, list(suggestion.get('warnings', []))
        for name, value in suggestion['suggested_attributes'].items():
            if name not in ATTRIBUTE_SPECS:
                continue
            kind, unit = ATTRIBUTE_SPECS[name]
            spec = dict(name=name, type=kind, unit=unit)
            if name in by_name and by_name[name] != spec:
                warnings.append(f'{name}: Typ oder Einheit der Kategorie weicht ab; Wert wurde nicht vorausgefüllt.')
                continue
            if name not in by_name:
                fields.append(spec)
                by_name[name] = spec
            attributes[name] = value
        part = {key: suggestion.get(key, '') for key in editable - {'attributes'}}
        part.update(category_id=category.id, attributes=attributes)
        duplicate = existing_part(article)
        staged = dict(token=secrets.token_hex(32), created=time.time(), article_number=article,
                      part=part, fields=fields, category_fields=category.fields, category_name=category.name,
                      product_url=suggestion['product_url'], datasheet_url=suggestion['datasheet_url'],
                      fetched_at=product['fetched_at'], cached=product['cached'], warnings=warnings,
                      existing_part=part_data(duplicate) if duplicate else None)
        g.auth.reichelt_preview = staged
        db.session.commit()
        return jsonify({key: value for key, value in staged.items() if key not in ('created', 'category_fields')})

    @app.post('/api/parts/reichelt/create')
    def create_reichelt_part():
        data = request.get_json()
        db.session.execute(update(User).values(username=User.username))
        db.session.refresh(g.auth)
        staged, token = g.auth.reichelt_preview, data.get('token')
        if not isinstance(token, str) or not staged or not secrets.compare_digest(token, staged['token']):
            raise ValueError('Reichelt-Produkt bitte zuerst erneut abrufen und prüfen.')
        if staged['created'] < time.time()-1800:
            raise ValueError('Die Produktvorschau ist abgelaufen. Bitte erneut abrufen.')
        if existing_part(staged['article_number']):
            abort(409, 'Dieser Reichelt-Artikel ist bereits vorhanden. Bitte das vorhandene Bauteil öffnen.')
        category = db.session.get(Category, staged['part']['category_id'])
        if not category or category.fields != staged['category_fields']:
            abort(409, 'Die Kategorie wurde seit der Vorschau geändert. Bitte Produktdaten erneut abrufen.')
        values, complete = data.get('part'), data.get('manual_complete', False)
        if not isinstance(values, dict) or set(values) - editable:
            raise ValueError('Ungültige Bauteildaten.')
        if not isinstance(complete, bool):
            raise ValueError('Vollständige manuelle Prüfung muss als Wahrheitswert angegeben werden.')
        # Only add compatible definitions when the reviewed part is actually saved.
        category.fields = validate(Category, {'fields': staged['fields']}, category)['fields']
        values = validate(Part, {**staged['part'], **values})
        part = Part(**values)
        db.session.add(part)
        db.session.flush()
        suppliers = reichelt_suppliers()
        supplier = suppliers[0] if suppliers else Supplier(name='Reichelt')
        if not suppliers:
            db.session.add(supplier)
            db.session.flush()
        offer = Offer(**validate(Offer, dict(part_id=part.id, supplier_id=supplier.id,
                      article_number=staged['article_number'], product_url=staged['product_url'],
                      datasheet_url=staged['datasheet_url'])))
        db.session.add(offer)
        mark_reichelt(part, staged['fetched_at'])
        if complete or values != staged['part']:
            mark_manual(part, 'complete' if complete else 'partial')
        g.auth.reichelt_preview = None
        db.session.commit()
        return jsonify(part_data(part)), 201
