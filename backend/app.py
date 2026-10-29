import csv
import hashlib
import io
import json
import math
import os
import secrets
import shutil
import sqlite3
import time
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import click
from flask import Flask, abort, g, jsonify, request, send_file
from sqlalchemy import event, select, func, or_, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.engine import Engine
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import dotenv_values
from .models import db, User, Session, Attempt, Category, CategoryNode, Location, Supplier, Part, Offer, Stock
from .curation import part_data, manual_status, mark_manual
from .categories import category_data, descendants

TABLES = {'categories': Category, 'locations': Location, 'suppliers': Supplier,
          'parts': Part, 'offers': Offer, 'stocks': Stock}


@event.listens_for(Engine, 'connect')
def configure_sqlite(conn, _):
    if isinstance(conn, sqlite3.Connection):
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=10000')

def row(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

def integer(value, label, minimum=1):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > 2**63-1:
        raise ValueError(f'{label}: ganze Zahl ab {minimum} erforderlich.')
    return value

def validate(model, data, existing=None):
    allowed = {c.name for c in model.__table__.columns} - {'id'}
    if set(data) - allowed:
        raise ValueError('Unbekannte Felder: ' + ', '.join(set(data)-allowed))
    result = {**(row(existing) if existing else {}), **data}
    result.pop('id', None)
    for col in model.__table__.columns:
        if col.name == 'id':
            continue
        value = result.get(col.name)
        if col.name in data and value is None and not col.nullable:
            raise ValueError(f'{col.name} darf nicht leer sein.')
        if not col.nullable and col.default is None and value is None:
            raise ValueError(f'{col.name} fehlt.')
        if isinstance(col.type, db.String) and value is not None:
            if not isinstance(value, str) or (col.type.length and len(value) > col.type.length):
                raise ValueError(f'{col.name}: ungültiger Text oder zu lang.')
            result[col.name] = value.strip()
        if col.name.endswith('_id') and value is not None:
            integer(value, col.name)
            target = next(iter(col.foreign_keys)).column.table.name
            cls = next(m for m in TABLES.values() if m.__tablename__ == target)
            if not db.session.get(cls, value):
                raise ValueError(f'{col.name}: Verweis existiert nicht.')
    if 'name' in result and not result['name']:
        raise ValueError('Name darf nicht leer sein.')
    if model is Category:
        if existing and db.session.get(CategoryNode, existing.id) and result.get('name') != existing.name:
            raise ValueError('Der Kategorienpfad von Reichelt bleibt unverändert. Technische Merkmale können bearbeitet werden.')
        fields = result.get('fields', [])
        if not isinstance(fields, list):
            raise ValueError('Merkmale müssen eine Liste sein.')
        names = set()
        for f in fields:
            if not isinstance(f, dict) or set(f) != {'name','type','unit'} or not isinstance(f['name'], str) or not f['name'].strip() or f['type'] not in ('text','number') or not isinstance(f['unit'], str) or f['name'] in names:
                raise ValueError('Merkmale benötigen eindeutige Namen, Typ text/number und Einheit.')
            names.add(f['name'])
        if existing:
            for p in db.session.scalars(select(Part).where(Part.category_id == existing.id)):
                validate_attributes(fields, p.attributes)
                old = {f['name']: f for f in existing.fields}
                new = {f['name']: f for f in fields}
                if any(old.get(k) != new.get(k) for k in p.attributes):
                    raise ValueError('Typ oder Einheit eines verwendeten Merkmals darf nicht verändert werden.')
    if model is Part:
        attrs = result.get('attributes', {})
        validate_attributes(db.session.get(Category, result['category_id']).fields, attrs)
    if model is Location and existing:
        parent = result.get('parent_id')
        seen = {existing.id}
        while parent:
            if parent in seen:
                raise ValueError('Lagerplatz-Hierarchie darf keinen Kreis enthalten.')
            seen.add(parent)
            parent = db.session.get(Location, parent).parent_id
    if model is Offer:
        for key in ('product_url', 'datasheet_url'):
            url = result.get(key, '')
            if url and (urlparse(url).scheme not in ('http','https') or not urlparse(url).netloc):
                raise ValueError('Links müssen vollständige HTTP(S)-Adressen sein.')
    if model is Stock:
        integer(result.get('quantity', 0), 'Menge', 0)
    return result

def validate_attributes(fields, attrs):
    if not isinstance(attrs, dict) or set(attrs) - {f['name'] for f in fields}:
        raise ValueError('Unbekannte oder ungültige technische Merkmale.')
    for f in fields:
        if f['name'] not in attrs:
            continue
        v = attrs[f['name']]
        if f['type'] == 'number':
            if isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v):
                raise ValueError(f"{f['name']}: endliche Zahl erforderlich.")
        elif not isinstance(v, str):
            raise ValueError(f"{f['name']}: Text erforderlich.")

def create_app(config=None):
    settings = {**dotenv_values(Path(__file__).resolve().parents[1]/'.env'), **os.environ}
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.update(SQLALCHEMY_DATABASE_URI=settings.get('DATABASE_URL', 'sqlite:///' + str(Path(app.instance_path)/'parts.sqlite')),
                      MAX_CONTENT_LENGTH=8*1024*1024, COOKIE_SECURE=settings.get('COOKIE_SECURE','1') == '1',
                      BACKUP_DIRECTORY=settings.get('PARTSDB_BACKUP_DIR') or str(Path(app.instance_path)/'backups'),
                      REICHELT_API_KEY=settings.get('REICHELT_API_KEY', ''),
                      REICHELT_SCRAPER_ENABLED=settings.get('REICHELT_SCRAPER_ENABLED', '1') == '1',
                      REICHELT_BROWSER_PATH=settings.get('REICHELT_BROWSER_PATH') or shutil.which('chromium') or shutil.which('google-chrome'))
    if config:
        app.config.update(config)
    db.init_app(app)
    if settings.get("TRUST_PROXY") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=0)

    @app.errorhandler(ValueError)
    def bad_value(e):
        db.session.rollback()
        return jsonify(error=str(e)), 400

    @app.errorhandler(IntegrityError)
    def conflict(e):
        db.session.rollback()
        return jsonify(error='Der Eintrag wird verwendet oder ein eindeutiger Wert existiert bereits.'), 409

    @app.errorhandler(OperationalError)
    def unavailable(e):
        db.session.rollback()
        app.logger.exception('Database operation failed')
        return jsonify(error='Datenbank vorübergehend nicht verfügbar.'), 503

    from werkzeug.exceptions import HTTPException
    @app.errorhandler(HTTPException)
    def http_error(e):
        db.session.rollback()
        return jsonify(error=e.description), e.code

    @app.before_request
    def authenticate():
        if not request.path.startswith('/api'):
            return
        if request.path == '/api/login' and request.method == 'POST':
            return
        if request.is_json and not isinstance(request.get_json(), dict):
            raise ValueError('Ein JSON-Objekt ist erforderlich.')
        token = request.cookies.get('parts_session','')
        s = db.session.get(Session, hashlib.sha256(token.encode()).hexdigest()) if token else None
        if not s or s.expires <= time.time():
            abort(401, 'Bitte anmelden.')
        g.auth = s
        if request.method not in ('GET','HEAD','OPTIONS') and not secrets.compare_digest(request.headers.get('X-CSRF-Token',''), s.csrf):
            abort(403, 'Ungültiger CSRF-Token. Bitte neu anmelden.')
        if request.method not in ('GET','HEAD','OPTIONS'):
            # Serialize writes before rechecking the session. A request waiting
            # behind an account change or reset must not write with a revoked login.
            db.session.execute(update(User).values(username=User.username))
            s = db.session.get(Session,s.id,populate_existing=True)
            if not s or s.expires <= time.time():
                abort(401, 'Bitte neu anmelden.')
            g.auth = s

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @app.post('/api/login')
    def login():
        if request.headers.get('Origin') and request.headers['Origin'].rstrip('/') != request.host_url.rstrip('/'):
            abort(403, 'Ungültiger Ursprung.')
        data = request.get_json()
        if not isinstance(data, dict): raise ValueError('Ein JSON-Objekt ist erforderlich.')
        if not isinstance(data.get('username'), str): raise ValueError('Benutzername erforderlich.')
        address = request.remote_addr or 'unknown'
        now = time.time()
        db.session.query(Attempt).filter(Attempt.at < now-900).delete()
        db.session.query(Session).filter(Session.expires < now).delete()
        if db.session.scalar(select(func.count()).select_from(Attempt).where(Attempt.address==address)) >= 5:
            db.session.commit()
            abort(429, 'Zu viele Anmeldeversuche. Bitte nach 15 Minuten erneut versuchen.')
        user = db.session.scalar(select(User).where(User.username==data.get('username')))
        password = data.get('password','')
        if not isinstance(password, str) or not user or not check_password_hash(user.password_hash, password):
            db.session.add(Attempt(address=address, at=now))
            db.session.commit()
            abort(401, 'Benutzername oder Passwort falsch.')
        token = secrets.token_hex(32)
        s = Session(id=hashlib.sha256(token.encode()).hexdigest(),user_id=user.id,csrf=secrets.token_hex(32),expires=now+43200)
        db.session.add(s)
        db.session.commit()
        response = jsonify(csrf=s.csrf, username=user.username)
        response.set_cookie('parts_session', token, secure=app.config['COOKIE_SECURE'], httponly=True, samesite='Strict', max_age=43200)
        return response

    @app.get('/api/session')
    def session_info():
        return jsonify(csrf=g.auth.csrf, username=db.session.get(User,g.auth.user_id).username)

    @app.post('/api/logout')
    def logout():
        db.session.delete(g.auth)
        db.session.commit()
        response = jsonify(ok=True)
        response.delete_cookie('parts_session')
        return response

    @app.route('/api/<entity>', methods=['GET','POST'])
    def collection(entity):
        if entity not in TABLES or entity in ('offers','stocks'):
            abort(404)
        model = TABLES[entity]
        if request.method == 'POST':
            data = dict(request.get_json())
            status = manual_status(data) if model is Part else None
            obj = model(**validate(model, data))
            db.session.add(obj)
            if model is Part:
                mark_manual(obj, status)
            db.session.commit()
            return jsonify(part_data(obj) if model is Part else category_data(obj) if model is Category else row(obj)), 201
        if model is not Part:
            if model is Category:
                nodes = {node.category_id:node for node in db.session.scalars(select(CategoryNode))}
                return jsonify([category_data(category, nodes) for category in db.session.scalars(select(Category).order_by(Category.name))])
            return jsonify([row(o) for o in db.session.scalars(select(model).order_by(model.name))])
        query = select(Part)
        if q := request.args.get('q','').strip():
            term = '%' + q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
            query = query.where(or_(*[c.ilike(term,escape='\\') for c in (Part.name,Part.mpn,Part.manufacturer,Part.description)], Part.id.in_(select(Offer.part_id).where(Offer.article_number.ilike(term,escape='\\')))))
        for arg, column in [('category_id',Part.category_id)]:
            if request.args.get(arg):
                query = query.where(column.in_(descendants(int(request.args[arg]))))
        stock_query = select(Stock.part_id)
        if request.args.get('location_id'):
            stock_query = stock_query.where(Stock.location_id==int(request.args['location_id']))
        if request.args.get('in_stock') == '1':
            stock_query = stock_query.where(Stock.quantity>0)
        if request.args.get('location_id') or request.args.get('in_stock')=='1':
            query = query.where(Part.id.in_(stock_query))
        if field := request.args.get('field'):
            if not request.args.get('category_id'):
                raise ValueError('Merkmalsfilter benötigen eine Kategorie.')
            cat = db.session.get(Category,int(request.args['category_id']))
            spec = next((f for f in cat.fields if f['name']==field), None) if cat else None
            if not spec:
                raise ValueError('Unbekanntes Merkmal.')
            compatible = [category.id for category in db.session.scalars(select(Category).where(Category.id.in_(descendants(cat.id))))
                          if any(candidate == spec for candidate in category.fields)]
            query = query.where(Part.category_id.in_(compatible))
            value = Part.attributes[field]
            if spec['type']=='number':
                for key, op in [('min',lambda a,b:a>=b),('max',lambda a,b:a<=b)]:
                    if request.args.get(key):
                        number = float(request.args[key])
                        if not math.isfinite(number): raise ValueError('Ungültiger Zahlenfilter.')
                        query = query.where(op(value.as_float(),number))
            elif request.args.get('value'):
                query = query.where(value.as_string()==request.args['value'])
        total = db.session.scalar(select(func.count()).select_from(query.subquery()))
        page = max(1,int(request.args.get('page',1)))
        sort = {'name':Part.name,'manufacturer':Part.manufacturer,'mpn':Part.mpn}.get(request.args.get('sort'),Part.name)
        sort = sort.desc() if request.args.get('direction')=='desc' else sort.asc()
        parts = db.session.scalars(query.order_by(sort,Part.id).offset((page-1)*25).limit(25)).all()
        result = []
        for p in parts:
            result.append({**part_data(p),'quantity':db.session.scalar(select(func.coalesce(func.sum(Stock.quantity),0)).where(Stock.part_id==p.id))})
        return jsonify(items=result,total=total,page=page,page_size=25)

    @app.route('/api/<entity>/<int:ident>', methods=['GET','PUT','DELETE'])
    def item(entity, ident):
        if entity not in TABLES or entity == 'stocks': abort(404)
        model = TABLES[entity]
        obj = db.get_or_404(model,ident)
        if request.method=='DELETE':
            if model is Category and db.session.get(CategoryNode, ident):
                raise ValueError('Reichelt-Kategorien gehören zum übernommenen Katalog und können nicht einzeln gelöscht werden.')
            if model is Part and request.args.get('confirm')!='yes':
                raise ValueError('Löschen des Bauteils und seiner Bestände muss bestätigt werden.')
            db.session.delete(obj)
            if model is Offer:
                mark_manual(db.session.get(Part, obj.part_id))
            db.session.commit()
            return jsonify(ok=True)
        if request.method=='PUT':
            data = dict(request.get_json())
            status = manual_status(data) if model is Part else None
            previous = row(obj)
            for k,v in validate(model,data,obj).items(): setattr(obj,k,v)
            if model is Part and (status is not None or row(obj) != previous):
                mark_manual(obj, status)
            elif model is Offer and row(obj) != previous:
                mark_manual(db.session.get(Part, obj.part_id))
            db.session.commit()
        result = part_data(obj) if model is Part else category_data(obj) if model is Category else row(obj)
        if model is Part:
            result['offers'] = [row(o) for o in db.session.scalars(select(Offer).where(Offer.part_id==ident))]
            result['stocks'] = [row(o) for o in db.session.scalars(select(Stock).where(Stock.part_id==ident))]
        return jsonify(result)

    @app.post('/api/parts/<int:ident>/offers')
    def add_offer(ident):
        db.get_or_404(Part,ident)
        data = {**request.get_json(),'part_id':ident}
        obj = Offer(**validate(Offer,data))
        db.session.add(obj)
        mark_manual(db.session.get(Part, ident))
        db.session.commit()
        return jsonify(row(obj)),201

    @app.post('/api/parts/<int:ident>/stock')
    def stock(ident):
        # Acquire the SQLite writer lock before reading; serializes competing stock operations.
        db.session.execute(update(Part).where(Part.id==ident).values(name=Part.name))
        db.get_or_404(Part,ident)
        data = request.get_json()
        action = data.get('action')
        quantity = integer(data.get('quantity'),'Menge',0 if action=='set' else 1)
        source = integer(data.get('location_id'),'Lagerplatz')
        db.get_or_404(Location,source)
        def at(location):
            s = db.session.scalar(select(Stock).where(Stock.part_id==ident,Stock.location_id==location))
            if not s:
                s = Stock(part_id=ident,location_id=location,quantity=0)
                db.session.add(s)
            return s
        s = at(source)
        if action=='add': s.quantity += quantity
        elif action=='set': s.quantity = quantity
        elif action in ('remove','transfer'):
            if s.quantity < quantity: raise ValueError('Nicht genügend Bestand.')
            if action=='transfer':
                target = integer(data.get('target_id'),'Ziellagerplatz')
                if target==source: raise ValueError('Quelle und Ziel müssen verschieden sein.')
                db.get_or_404(Location,target)
                destination_stock = at(target)
                destination_stock.quantity += quantity
                integer(destination_stock.quantity, 'Zielbestand', 0)
            s.quantity -= quantity
        else: raise ValueError('Unbekannte Bestandsaktion.')
        integer(s.quantity, 'Resultierender Bestand', 0)
        db.session.commit()
        return jsonify(ok=True)

    from .demands import register_demands
    from .part_import import register_part_import
    from .maintenance import register_maintenance
    register_maintenance(app)
    register_part_import(app, validate)
    preview_reichelt = register_demands(app, integer, validate, row)
    register_csv(app, preview_reichelt)
    register_cli(app)
    return app

def read_csv(source, expected_name=None):
    label = expected_name+'.csv' if expected_name else 'CSV-Datei'
    try:
        text = source.decode('utf-8-sig')
    except UnicodeError as e:
        raise ValueError(f'{label}: Bitte als CSV in UTF-8 speichern.') from e
    delimiters = (',', ';', '\t')
    stream = io.StringIO(text, newline='')
    first_line = stream.readline().rstrip('\r\n')
    line_offset = 0
    if first_line.lower().startswith('sep='):
        delimiter = first_line[4:]
        if delimiter not in delimiters:
            raise ValueError(f'{label}: Unterstützte Trennzeichen sind Komma, Semikolon und Tabulator.')
        delimiters = (delimiter,)
        text = stream.read()
        line_offset = 1
    for delimiter in delimiters:
        reader = csv.DictReader(io.StringIO(text, newline=''), delimiter=delimiter, strict=True)
        try:
            header = reader.fieldnames
        except csv.Error:
            continue
        for name, model in TABLES.items():
            if expected_name is not None and name != expected_name:
                continue
            if header == [column.name for column in model.__table__.columns]:
                return name, reader, line_offset
    raise ValueError(f'{label}: CSV-Kopfzeile nicht erkannt. Bitte die dokumentierten Spalten verwenden. '
                     'Komma, Semikolon und Tabulator werden automatisch erkannt; '
                     'Anführungszeichen innerhalb eines Textfelds als "" schreiben.')


def csv_records(reader, name, line_offset):
    while True:
        try:
            record = next(reader)
        except StopIteration:
            return
        except csv.Error as e:
            raise ValueError(f'{name}.csv, Zeile {reader.reader.line_num+line_offset}: Ungültiges CSV-Format. '
                             'Bitte Anführungszeichen und Trennzeichen prüfen. '
                             'Anführungszeichen innerhalb eines Textfelds als "" schreiben, '
                             'z. B. "Bauteil ""A""".') from e
        yield reader.line_num+line_offset, record


def csv_sources(payload):
    if zipfile.is_zipfile(io.BytesIO(payload)):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            expected = {name+'.csv' for name in TABLES}
            if set(archive.namelist()) != expected or len(archive.infolist()) != len(expected):
                raise ValueError('Das ZIP muss genau die sechs dokumentierten CSV-Dateien enthalten.')
            if sum(f.file_size for f in archive.infolist()) > 32*1024*1024:
                raise ValueError('Entpackte CSV-Dateien sind zu groß (maximal 32 MB).')
            sources = {}
            for name in TABLES:
                _, reader, line_offset = read_csv(archive.read(name+'.csv'), name)
                sources[name] = (reader, line_offset)
            return sources
    name, reader, line_offset = read_csv(payload)
    return {name: (reader, line_offset)}


def register_csv(app, preview_reichelt):
    @app.get('/api/export')
    def export():
        archive = io.BytesIO()
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name, model in TABLES.items():
                output = io.StringIO(newline='')
                fields = [c.name for c in model.__table__.columns]
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                for obj in db.session.scalars(select(model).order_by(model.id)):
                    values = row(obj)
                    for col in model.__table__.columns:
                        if isinstance(col.type, db.JSON): values[col.name] = json.dumps(values[col.name],ensure_ascii=False)
                        elif values[col.name] is None: values[col.name] = ''
                    writer.writerow(values)
                z.writestr(name+'.csv',output.getvalue())
        archive.seek(0)
        return send_file(archive,mimetype='application/zip',as_attachment=True,download_name='partsdb-export.zip')

    @app.post('/api/import')
    def import_csv():
        upload = request.files.get('file')
        if not upload: raise ValueError('CSV-Datei fehlt.')
        payload = upload.read()
        from .reichelt import looks_like_list
        if request.form.get('format') == 'reichelt' or looks_like_list(payload):
            return preview_reichelt(payload, upload.filename, request.form.get('project_name'))
        digest = hashlib.sha256(payload).hexdigest()
        apply = request.form.get('apply')=='yes'
        db.session.execute(update(User).values(username=User.username))
        snapshot = {name: [row(o) for o in db.session.scalars(select(model).order_by(model.id))] for name,model in TABLES.items()}
        state = hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if apply and (request.form.get('digest') != digest or g.auth.import_digest != digest):
            raise ValueError('Bitte dieselbe Datei zuerst prüfen.')
        if apply and g.auth.import_state != state:
            raise ValueError('Der Bestand wurde seit der Vorschau verändert. Bitte Datei erneut prüfen.')
        summary, changes = {}, []
        try:
            for name, (reader, line_offset) in csv_sources(payload).items():
                model = TABLES[name]
                columns = list(model.__table__.columns)
                seen, new, changed = set(), 0, 0
                pending = []
                for line, record in csv_records(reader, name, line_offset):
                    try:
                        if None in record or any(v is None for v in record.values()):
                            raise ValueError('Ungültige Spaltenanzahl.')
                        values = {}
                        for col in columns:
                            raw = record[col.name]
                            if isinstance(col.type, db.Integer):
                                values[col.name] = None if raw=='' and col.nullable else int(raw)
                            elif isinstance(col.type, db.JSON): values[col.name] = json.loads(raw)
                            else: values[col.name] = raw
                        ident = integer(values.pop('id'),'ID')
                        if ident in seen: raise ValueError('Doppelte ID.')
                        seen.add(ident)
                        obj = db.session.get(model,ident)
                        before = row(obj) if obj else None
                        # Parents can occur after children in the CSV; resolve hierarchy in a second pass.
                        parent = values.get('parent_id') if model is Location else None
                        if model is Location: values['parent_id'] = None
                        valid = validate(model, values, obj)
                        if obj:
                            for k,v in valid.items(): setattr(obj,k,v)
                        else:
                            obj = model(id=ident,**valid)
                            db.session.add(obj)
                            new += 1
                        db.session.flush()
                        if model is Location: pending.append((obj,parent,line,before))
                        elif before and before != row(obj):
                            changed += 1
                            changes.append({'file':name+'.csv','line':line,'id':ident,'before':before,'after':row(obj)})
                    except (ValueError,TypeError,IntegrityError) as e:
                        raise ValueError(f'{name}.csv, Zeile {line}: {e if not isinstance(e,IntegrityError) else "Doppelter Wert oder ungültiger Verweis."}') from e
                for obj,parent,line,before in pending:
                    try:
                        obj.parent_id = validate(Location,{'parent_id':parent},obj)['parent_id']
                        db.session.flush()
                        if before and before != row(obj):
                            changed += 1
                            changes.append({'file':name+'.csv','line':line,'id':obj.id,'before':before,'after':row(obj)})
                    except ValueError as e:
                        raise ValueError(f'{name}.csv, Zeile {line}: {e}') from e
                summary[name] = {'new':new,'changed':changed,'rows':len(seen)}
            if apply:
                g.auth.import_digest = None
                g.auth.import_state = None
                db.session.commit()
            else:
                db.session.rollback()
                g.auth.import_digest = digest
                g.auth.import_state = state
                db.session.commit()
        except (zipfile.BadZipFile,UnicodeError,csv.Error,RuntimeError) as e:
            db.session.rollback()
            raise ValueError('Ungültige CSV-Datei oder ungültiges ZIP: '+str(e)) from e
        return jsonify(digest=digest,summary=summary,changes=changes,applied=apply)


def register_cli(app):
    @app.cli.command('migrate')
    def migrate():
        """Apply versioned schema migrations."""
        from alembic.config import Config
        from alembic import command
        cfg = Config(str(Path(__file__).parent/'alembic.ini'))
        cfg.set_main_option('script_location',str(Path(__file__).parent/'migrations'))
        cfg.attributes['connection'] = db.engine.connect()
        try: command.upgrade(cfg,'head')
        finally: cfg.attributes['connection'].close()
        click.echo('Datenbank ist aktuell.')

    @app.cli.command('set-user')
    @click.option('--username',prompt='Benutzername')
    @click.option('--allow-short-password',is_flag=True,help='Kurzes Passwort ab vier Zeichen für die lokale Einrichtung ausdrücklich erlauben.')
    @click.password_option(confirmation_prompt=True)
    def set_user(username,password,allow_short_password):
        """Create the single account or reset its password; revoke all sessions."""
        minimum = 4 if allow_short_password else 12
        if not username.strip() or len(username)>100 or len(password)<minimum:
            raise click.ClickException(f'Benutzername erforderlich; Passwort mindestens {minimum} Zeichen.')
        db.session.execute(update(User).values(username=User.username))
        user = db.session.scalar(select(User))
        if not user:
            user = User()
            db.session.add(user)
        user.username = username.strip()
        user.password_hash = generate_password_hash(password)
        db.session.query(Session).delete()
        db.session.commit()
        click.echo('Konto gespeichert; bestehende Sitzungen beendet.')

    @app.cli.command('reset-data')
    @click.option('--yes',is_flag=True,help='Das Löschen der Inventardaten ausdrücklich bestätigen.')
    def reset_data(yes):
        """Back up and erase inventory; keep categories, definitions and account."""
        if not yes:
            click.confirm('Bauteile, Bestände, Projektlisten, Lagerplätze und Lieferanten löschen? Kategorien und Konto bleiben erhalten.',abort=True)
        from .maintenance import reset_inventory
        _,backup = reset_inventory(app)
        click.echo(f'Inventardaten zurückgesetzt. Kategorien und Konto erhalten. Sicherung: {backup}')

    @app.cli.command('backup')
    @click.argument('directory', type=click.Path(path_type=Path))
    def backup(directory):
        """Consistent SQLite backup; retain backups for 14 days."""
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        destination = directory / ('partsdb-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite')
        source = db.engine.raw_connection()
        try:
            with closing(sqlite3.connect(destination)) as target:
                source.driver_connection.backup(target)
            destination.chmod(0o600)
        finally: source.close()
        for file in directory.glob('partsdb-*.sqlite'):
            if file.stat().st_mtime < time.time()-14*86400: file.unlink()
        click.echo(str(destination))
