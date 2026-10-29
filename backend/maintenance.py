"""Account maintenance and an inventory reset with a consistent SQLite backup."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time

from flask import abort, g, jsonify, request
from sqlalchemy import select, update
from werkzeug.security import check_password_hash, generate_password_hash

from .models import (db, User, Session, Attempt, Category, CategoryNode, Part, Offer, Stock,
                     Location, Supplier, DemandList, DemandItem, GoodsReceipt, PartCuration,
                     ProductCache, ProductFetchState)

ERASE = {'receipts':GoodsReceipt, 'demand_items':DemandItem, 'demand_lists':DemandList,
         'curation':PartCuration, 'stocks':Stock, 'offers':Offer, 'parts':Part,
         'locations':Location, 'suppliers':Supplier, 'product_cache':ProductCache}


def snapshot():
    digest, counts = hashlib.sha256(), {}
    for name,model in {**ERASE,'categories':Category,'category_nodes':CategoryNode,'accounts':User}.items():
        count = 0
        digest.update(name.encode()+b'\n')
        for row in db.session.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns)).mappings():
            digest.update(json.dumps(dict(row),sort_keys=True,ensure_ascii=False).encode()+b'\n')
            count += 1
        counts[name] = count
    return counts,digest.hexdigest()


def backup_database(directory):
    # A distinct read-only connection can back up the committed database while
    # our writer reservation prevents another request from changing inventory.
    database = db.engine.url.database
    if db.engine.dialect.name != 'sqlite' or not database or database == ':memory:':
        raise ValueError('Sicherung benötigt eine dateibasierte SQLite-Datenbank.')
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    filename = 'partsdb-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite'
    destination = directory/filename
    descriptor = os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.close(descriptor)
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True,timeout=10)) as source:
        with closing(sqlite3.connect(destination)) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Datenbanksicherung konnte nicht verifiziert werden.')
    return destination


def reset_inventory(app, expected=None):
    db.session.execute(update(User).values(username=User.username))
    state = db.session.get(ProductFetchState,1,populate_existing=True)
    if state and state.lease_until > time.time():
        abort(409,'Es läuft noch ein Reichelt-Abruf. Bitte den Lauf stoppen und nach dem aktuellen Artikel erneut versuchen.')
    counts,current = snapshot()
    if expected and not secrets.compare_digest(expected,current):
        abort(409,'Die Daten wurden seit der Vorschau geändert. Bitte die Reset-Vorschau erneut öffnen.')
    try:
        backup = backup_database(app.config['BACKUP_DIRECTORY'])
    except (OSError,sqlite3.Error,ValueError) as error:
        db.session.rollback()
        app.logger.exception('Inventory reset backup failed')
        abort(503,'Die Sicherung konnte nicht erstellt werden. Es wurden keine Daten gelöscht.')
    for model in ERASE.values():
        db.session.query(model).delete(synchronize_session=False)
    db.session.query(Session).delete(synchronize_session=False)
    db.session.query(Attempt).delete(synchronize_session=False)
    if state:
        state.lease,state.lease_until,state.last_started,state.blocked_until = '',0,0,0
    else:
        db.session.add(ProductFetchState(id=1))
    db.session.commit()
    return counts,backup


def require_password(value):
    user = db.session.get(User,g.auth.user_id,populate_existing=True)
    if not isinstance(value,str) or not check_password_hash(user.password_hash,value):
        raise ValueError('Das aktuelle Passwort ist nicht korrekt.')
    return user


def register_maintenance(app):
    @app.put('/api/account')
    def change_account():
        data = request.get_json()
        user = require_password(data.get('current_password'))
        username = data.get('username')
        password = data.get('new_password','')
        if not isinstance(username,str) or not username.strip() or len(username)>100:
            raise ValueError('Benutzername mit 1 bis 100 Zeichen erforderlich.')
        if not isinstance(password,str) or (password and len(password)<12):
            raise ValueError('Das neue Passwort muss mindestens zwölf Zeichen haben.')
        user.username = username.strip()
        if password:
            user.password_hash = generate_password_hash(password)
        db.session.query(Session).delete(synchronize_session=False)
        db.session.commit()
        response = jsonify(ok=True,username=user.username)
        response.delete_cookie('parts_session')
        return response

    @app.post('/api/settings/reset/preview')
    def preview_reset():
        counts,state = snapshot()
        token = secrets.token_hex(32)
        g.auth.reset_preview = dict(token=token,created=time.time(),state=state)
        db.session.commit()
        return jsonify(token=token,delete={key:counts[key] for key in ERASE},
                       preserve={key:counts[key] for key in ('categories','category_nodes','accounts')})

    @app.post('/api/settings/reset')
    def reset_data():
        data = request.get_json()
        require_password(data.get('current_password'))
        staged,token = g.auth.reset_preview,data.get('token')
        if not isinstance(token,str) or not staged or not secrets.compare_digest(staged['token'],token):
            raise ValueError('Bitte zuerst die Reset-Vorschau öffnen.')
        if staged['created'] < time.time()-600:
            raise ValueError('Die Reset-Vorschau ist abgelaufen. Bitte erneut öffnen.')
        if data.get('confirmation') != 'ZURÜCKSETZEN':
            raise ValueError('Zum Bestätigen ZURÜCKSETZEN eingeben.')
        _,backup = reset_inventory(app,staged['state'])
        response = jsonify(ok=True,backup=backup.name)
        response.delete_cookie('parts_session')
        return response
