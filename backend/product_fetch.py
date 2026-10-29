"""Fetch public product data in a regular browser, with persistent cache and limits."""
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import tempfile
import time

from flask import abort
from sqlalchemy import select, update

from .models import db, User, ProductCache, ProductFetchState
from .reichelt import article_key, describe_product


class ScraperError(ValueError):
    def __init__(self, message, blocked=False):
        super().__init__(message)
        self.blocked = blocked


def available(app):
    return bool(app.config.get('REICHELT_SCRAPER_ENABLED') and app.config.get('REICHELT_BROWSER_PATH')
                and shutil.which('node') and (Path(__file__).resolve().parents[1]/'frontend/node_modules/playwright/index.mjs').is_file())


def scrape_product(article, url, browser_path, allow_mpn=False):
    script = Path(__file__).with_name('reichelt_scraper.mjs')
    with tempfile.TemporaryDirectory(prefix='partsdb-scraper-') as directory:
        try:
            process = subprocess.Popen([shutil.which('node') or 'node', str(script), article, url or '', browser_path,
                                        'identifier' if allow_mpn else 'article'],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                                       start_new_session=True, env={**os.environ, 'XDG_CACHE_HOME':directory})
        except OSError as error:
            raise ScraperError('Browserprozess konnte nicht gestartet werden. Backend-Konfiguration prüfen.') from error
        try:
            output, _ = process.communicate(timeout=28)
        except subprocess.TimeoutExpired as error:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise ScraperError('Reichelt-Abruf hat zu lange gedauert. Bitte später erneut versuchen.') from error
    try:
        result = json.loads(output) if len(output) <= 2*1024*1024 else {}
    except json.JSONDecodeError as error:
        raise ScraperError('Browser-Scraper konnte nicht gestartet werden. Node.js, Playwright und Chromium prüfen.') from error
    if not isinstance(result, dict):
        raise ScraperError('Ungültige Antwort des Browser-Scrapers.')
    if result.get('error'):
        raise ScraperError(str(result['error'])[:500], result.get('status') in (403, 429, 503))
    data = result.get('data')
    if not isinstance(data, dict) or not data.get('articleNumber') or not (
            article_key(str(data.get('articleNumber', ''))) == article_key(article) or
            (allow_mpn and article_key(str(data.get('mpn', ''))) == article_key(article))):
        raise ScraperError('Produktseite konnte nicht exakt dieser Artikelnummer oder Herstellerteilenummer zugeordnet werden.')
    return data


def get_product(app, article, known_url='', allow_mpn=False):
    if not isinstance(article, str) or not article.strip() or len(article) > 200:
        raise ValueError('Artikelnummer oder Herstellerteilenummer mit 1 bis 200 Zeichen erforderlich.')
    article = article_key(article)
    now = time.time()
    db.session.execute(update(User).values(username=User.username))
    cached = db.session.get(ProductCache, article)
    if (not cached or cached.fetched_at <= now-86400) and allow_mpn:
        matches = [item for item in db.session.scalars(select(ProductCache).where(ProductCache.fetched_at > now-86400))
                   if article_key(str(item.data.get('mpn', ''))) == article]
        if len(matches) > 1:
            raise ValueError('Mehrere Reichelt-Artikel mit dieser Herstellerteilenummer. Bitte die Reichelt-Artikelnummer verwenden.')
        if matches:
            cached = matches[0]
    if cached and cached.fetched_at > now-86400:
        result = dict(suggestion=describe_product(cached.data, cached.article_number), article_number=cached.article_number,
                      fetched_at=cached.fetched_at, cached=True)
        db.session.rollback()
        return result
    if not available(app):
        raise ValueError('Direkter Reichelt-Abruf benötigt Node.js, Playwright und Chromium auf dem Backend-Rechner.')
    state = db.session.get(ProductFetchState, 1)
    if state.lease_until > now:
        abort(429, 'Ein Produktabruf läuft bereits. Bitte kurz warten und erneut versuchen.')
    if state.blocked_until > now or state.last_started > now-3:
        abort(429, 'Reichelt-Abrufe sind kurz pausiert. Bitte später erneut versuchen.')
    lease = secrets.token_hex(24)
    state.lease, state.lease_until, state.last_started = lease, now+40, now
    db.session.commit()
    blocked = False
    try:
        data = (scrape_product(article, known_url, app.config['REICHELT_BROWSER_PATH'], allow_mpn=True) if allow_mpn else
                scrape_product(article, known_url, app.config['REICHELT_BROWSER_PATH']))
        actual_article = article_key(data['articleNumber'])
        suggestion = describe_product(data, actual_article)
        fetched_at = time.time()
        db.session.execute(update(User).values(username=User.username))
        cached = db.session.get(ProductCache, actual_article)
        if cached:
            cached.data, cached.fetched_at = data, fetched_at
        else:
            db.session.add(ProductCache(article_number=actual_article, fetched_at=fetched_at, data=data))
        db.session.commit()
        return dict(suggestion=suggestion, article_number=actual_article, fetched_at=fetched_at, cached=False)
    except ScraperError as error:
        blocked = error.blocked
        raise
    finally:
        db.session.rollback()
        db.session.execute(update(ProductFetchState).where(ProductFetchState.id == 1, ProductFetchState.lease == lease).values(
            lease='', lease_until=0, blocked_until=time.time()+60 if blocked else 0))
        db.session.commit()
