"""Reviewable product-data completion for already imported project positions."""
import secrets
import time

from flask import abort, g, jsonify, request
from sqlalchemy import select, update
from werkzeug.exceptions import TooManyRequests

from .models import db, User, Session, Category, Part, Offer, Supplier, DemandList, DemandItem, ProductFetchState
from .product_fetch import get_product, available, ScraperError
from .reichelt import ATTRIBUTE_SPECS, article_key
from .curation import mark_reichelt, part_data
from .categories import resolve_category, default_category, category_data


def register_enrichment(app, integer, validate, row, fingerprint, list_data):
    def position(list_id, item_id):
        demand = db.get_or_404(DemandList, list_id)
        item = db.get_or_404(DemandItem, integer(item_id, 'Position'))
        if item.list_id != demand.id:
            raise ValueError('Position gehört nicht zu dieser Projektliste.')
        part = db.get_or_404(Part, item.part_id)
        supplier_ids = [supplier.id for supplier in db.session.scalars(select(Supplier))
                        if article_key(supplier.name) in ('REICHELT', 'REICHELT ELEKTRONIK')]
        offers = [offer for offer in db.session.scalars(select(Offer).where(Offer.part_id == part.id,
                  Offer.supplier_id.in_(supplier_ids)).order_by(Offer.id))
                  if article_key(offer.article_number) == article_key(item.article_number)]
        if not offers:
            raise ValueError('Das Reichelt-Angebot dieser Position fehlt. Bitte zuerst beim Bauteil ergänzen.')
        return demand, item, part, offers[0]

    def candidates(part, offer, suggestion):
        changes = []
        current_category = db.session.get(Category, part.category_id)
        target = resolve_category(suggestion, current_category)
        old_specs = {field['name']: field for field in current_category.fields}
        new_specs = {field['name']: field for field in target.fields}
        can_change_category = all(name not in new_specs or old_specs.get(name) == new_specs.get(name) for name in part.attributes)
        def add(key, label, before, after, selected, unit='', allowed=True, reason=''):
            if after not in ('', None) and before != after:
                changes.append(dict(key=key, label=label, before=before, after=after, selected=selected and allowed,
                                    unit=unit, allowed=allowed, reason=reason))
        add('category_id', 'Kategorie', current_category.name, target.name,
            current_category.id == default_category().id, allowed=can_change_category,
            reason='' if can_change_category else 'Vorhandene Merkmale passen nicht zur vorgeschlagenen Kategorie.')
        for key, label in [('name','Bezeichnung'), ('manufacturer','Hersteller'), ('mpn','Herstellerteilenummer'),
                           ('package','Bauform'), ('description','Beschreibung')]:
            before, after = getattr(part, key), suggestion.get(key, '')
            add(key, label, before, after, not before or (key == 'name' and article_key(before) == article_key(offer.article_number)))
        for key, label in [('product_url','Produktlink'), ('datasheet_url','Datenblattlink')]:
            before = getattr(offer, key)
            add(key, label, before, suggestion.get(key, ''), not before)
        for name, value in suggestion['suggested_attributes'].items():
            if name not in ATTRIBUTE_SPECS:
                continue
            kind, unit = ATTRIBUTE_SPECS[name]
            existing = new_specs.get(name)
            allowed = not existing or (existing['type'] == kind and existing['unit'] == unit)
            add('attribute:'+name, name, part.attributes.get(name), value, name not in part.attributes, unit,
                allowed, '' if allowed else 'Typ oder Einheit des vorhandenen Merkmals weicht ab.')
        return changes, target.id

    def save_changes(part, offer, possible, category_id, selected, fetched_at):
        category_id = category_id if 'category_id' in selected else part.category_id
        category = db.get_or_404(Category, category_id)
        fields = [dict(field) for field in category.fields]
        if 'category_id' in selected:
            old_fields = db.session.get(Category, part.category_id).fields
            existing_names = {field['name'] for field in fields}
            fields.extend(dict(field) for field in old_fields if field['name'] in part.attributes and field['name'] not in existing_names)
        by_name = {field['name']:field for field in fields}
        attributes = dict(part.attributes)
        for key in selected:
            if not key.startswith('attribute:'):
                continue
            name = key.removeprefix('attribute:')
            kind, unit = ATTRIBUTE_SPECS[name]
            spec = dict(name=name,type=kind,unit=unit)
            if name in by_name and by_name[name] != spec:
                raise ValueError(f'{name}: Typ oder Einheit der Zielkategorie passt nicht. Kategorie oder Auswahl prüfen.')
            if name not in by_name:
                fields.append(spec)
                by_name[name] = spec
            attributes[name] = possible[key]['after']
        if fields != category.fields:
            category.fields = validate(Category, {'fields':fields}, category)['fields']
        values = {key:possible[key]['after'] for key in selected if key in ('name','manufacturer','mpn','package','description')}
        values.update(category_id=category_id, attributes=attributes)
        for key,value in validate(Part,values,part).items():
            setattr(part,key,value)
        offer_values = {key:possible[key]['after'] for key in selected if key in ('product_url','datasheet_url')}
        for key,value in validate(Offer,offer_values,offer).items():
            setattr(offer,key,value)
        mark_reichelt(part, fetched_at)
        return category

    @app.post('/api/demands/<int:ident>/enrich/auto')
    def enrich_automatically(ident):
        # One atomic position per request keeps long lists within HTTP timeouts
        # and allows the browser to show progress and stop between positions.
        demand, item, part, offer = position(ident, request.get_json().get('item_id'))
        item_id, part_id, offer_id, session_id = item.id, part.id, offer.id, g.auth.id
        before = fingerprint()
        article, known_url = item.article_number, offer.product_url
        db.session.rollback()
        try:
            product = get_product(app, article, known_url)
        except ScraperError as error:
            db.session.rollback()
            return jsonify(error=str(error), blocked=error.blocked), 400
        except TooManyRequests as error:
            db.session.rollback()
            state = db.session.get(ProductFetchState, 1)
            blocked = state.blocked_until > time.time()
            delay = max(1, int(state.blocked_until-time.time())+1) if blocked else 3
            db.session.rollback()
            return jsonify(error=error.description, blocked=blocked, retry_after=delay), 429
        db.session.execute(update(User).values(username=User.username))
        db.session.expire_all()
        session = db.session.get(Session, session_id, populate_existing=True)
        if not session or session.expires <= time.time():
            abort(401, 'Bitte neu anmelden.')
        g.auth = session
        demand, item, part, offer = position(ident, item_id)
        if part.id != part_id or offer.id != offer_id or before != fingerprint():
            abort(409, 'Bauteildaten wurden während des Abrufs verändert. Diese Position bitte erneut vervollständigen.')
        suggestion = product['suggestion']
        changes, target_id = candidates(part, offer, suggestion)
        selected = [change['key'] for change in changes if change['selected'] and change['allowed']]
        actual_category = db.get_or_404(Category, target_id if 'category_id' in selected else part.category_id)
        specs = {field['name']:field for field in actual_category.fields}
        warnings = list(suggestion.get('warnings', []))
        for change in changes:
            if not change['allowed']:
                warnings.append(change['label']+': '+change['reason'])
        for key in list(selected):
            if key.startswith('attribute:'):
                name = key.removeprefix('attribute:')
                kind, unit = ATTRIBUTE_SPECS[name]
                spec = dict(name=name, type=kind, unit=unit)
                if name in specs and specs[name] != spec:
                    selected.remove(key)
                    warnings.append(name+': vorhandener Typ oder Einheit bleibt erhalten; Wert nicht übernommen.')
        possible = {change['key']:change for change in changes if change['allowed']}
        category = save_changes(part, offer, possible, target_id, selected, product['fetched_at'])
        db.session.commit()
        return jsonify(item_id=item_id, article_number=article, part=part_data(part), category=category_data(category),
                       changed=selected, warnings=warnings, cached=product['cached'])

    @app.post('/api/demands/<int:ident>/enrich')
    def preview(ident):
        demand, item, part, offer = position(ident, request.get_json().get('item_id'))
        item_id, part_id, offer_id, session_id = item.id, part.id, offer.id, g.auth.id
        before = fingerprint()
        article, known_url = item.article_number, offer.product_url
        db.session.rollback()
        product = get_product(app, article, known_url)
        db.session.execute(update(User).values(username=User.username))
        db.session.expire_all()
        session = db.session.get(Session, session_id, populate_existing=True)
        if not session or session.expires <= time.time():
            abort(401, 'Bitte neu anmelden.')
        g.auth = session
        demand, item, part, offer = position(ident, item_id)
        if part.id != part_id or offer.id != offer_id or before != fingerprint():
            abort(409, 'Bauteildaten wurden während des Abrufs verändert. Bitte Vorschläge erneut abrufen.')
        suggestion = product['suggestion']
        changes, category_id = candidates(part, offer, suggestion)
        staged = dict(token=secrets.token_hex(32), created=time.time(), state=fingerprint(), list_id=ident,
                      item_id=item.id, part_id=part.id, offer_id=offer.id, category_id=category_id,
                      changes=changes, suggestion=suggestion, fetched_at=product['fetched_at'], cached=product['cached'])
        g.auth.enrichment_preview = staged
        db.session.commit()
        return jsonify(token=staged['token'], item_id=item_id, article_number=article, changes=changes,
                       warnings=suggestion.get('warnings', []), source_url=suggestion.get('product_url',''),
                       fetched_at=product['fetched_at'], cached=product['cached'])

    @app.post('/api/demands/<int:ident>/enrich/apply')
    def apply(ident):
        data = request.get_json()
        db.session.execute(update(User).values(username=User.username))
        db.session.refresh(g.auth)
        staged = g.auth.enrichment_preview
        token = data.get('token')
        if not isinstance(token,str) or not staged or not secrets.compare_digest(token,staged['token']) or staged['list_id'] != ident:
            raise ValueError('Produktvorschläge bitte zuerst erneut abrufen.')
        if staged['created'] < time.time()-1800:
            raise ValueError('Produktvorschläge sind abgelaufen. Bitte erneut abrufen.')
        if staged['state'] != fingerprint():
            abort(409, 'Bauteile oder Stammdaten wurden seit der Vorschau verändert. Bitte Vorschläge erneut abrufen.')
        demand, item, part, offer = position(ident, staged['item_id'])
        if part.id != staged['part_id'] or offer.id != staged['offer_id']:
            abort(409, 'Die Zuordnung der Projektposition wurde geändert. Bitte erneut abrufen.')
        selected = data.get('selected')
        possible = {change['key']:change for change in staged['changes'] if change['allowed']}
        if not isinstance(selected,list) or (not selected and staged['changes']) or not all(isinstance(key,str) for key in selected):
            raise ValueError('Mindestens eine Änderung auswählen.')
        if len(set(selected)) != len(selected) or set(selected)-possible.keys():
            raise ValueError('Ungültige Auswahl von Produktvorschlägen.')
        save_changes(part, offer, possible, staged['category_id'], selected, staged['fetched_at'])
        g.auth.enrichment_preview = None
        db.session.commit()
        return jsonify(list_data(demand,True))
