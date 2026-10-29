"""Headerless Reichelt lists and optional product suggestions from everydata.io."""
import csv
import io
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


def article_key(value):
    return ' '.join(value.split()).upper()


def parse_list(payload):
    try:
        text = payload.decode('utf-8-sig')
    except UnicodeError as error:
        raise ValueError('Reichelt-Liste bitte als UTF-8-CSV speichern.') from error
    stream = io.StringIO(text, newline='')
    first = stream.readline().rstrip('\r\n')
    offset = 1 if first.lower() == 'sep=;' else 0
    if not offset:
        stream.seek(0)
    reader = csv.reader(stream, delimiter=';', strict=True)
    items = {}
    try:
        for record in reader:
            if not record or all(not value.strip() for value in record):
                continue
            line = reader.line_num+offset
            if len(record) not in (2, 3):
                raise ValueError(f'Reichelt-CSV, Zeile {line}: Artikelnummer;Menge;optionaler Zusatz erwartet.')
            article = article_key(record[0])
            quantity = record[1].strip()
            if not article or len(article) > 200 or not re.fullmatch(r'[0-9]+', quantity):
                raise ValueError(f'Reichelt-CSV, Zeile {line}: Artikelnummer und positive ganze Menge erforderlich.')
            quantity = int(quantity)
            if not 1 <= quantity <= 2**63-1:
                raise ValueError(f'Reichelt-CSV, Zeile {line}: Menge außerhalb des gültigen Bereichs.')
            note = record[2] if len(record) == 3 else ''
            if article in items:
                items[article]['quantity'] += quantity
                if items[article]['quantity'] > 2**63-1:
                    raise ValueError(f'Reichelt-CSV, Zeile {line}: Gesamtmenge ist zu groß.')
                if note:
                    items[article]['note'] += ('\n' if items[article]['note'] else '')+note
            else:
                items[article] = dict(article_number=article, quantity=quantity, note=note)
            if len(items) > 1000:
                raise ValueError('Maximal 1000 unterschiedliche Positionen je Reichelt-Liste.')
    except csv.Error as error:
        raise ValueError(f'Reichelt-CSV, Zeile {reader.line_num+offset}: Anführungszeichen prüfen; '
                         'Anführungszeichen im Text als "" schreiben.') from error
    if not items:
        raise ValueError('Die Reichelt-Liste enthält keine Positionen.')
    return list(items.values())


def looks_like_list(payload):
    try:
        text = payload.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(text, newline=''), delimiter=';', strict=True)
        for record in reader:
            if not record or record == ['sep=', '']:
                continue
            return len(record) in (2, 3) and bool(re.fullmatch(r'[0-9]+', record[1].strip()))
    except (UnicodeError, csv.Error):
        pass
    return False


def api_get(endpoint, params, key):
    request = Request('https://api.everydata.io/rch/'+endpoint+'?'+urlencode(params),
                      headers={'x-api-key': key, 'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=8) as response:
            payload = response.read(2*1024*1024+1)
            if len(payload) > 2*1024*1024:
                raise ValueError('Produktdatenantwort ist zu groß.')
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError('Ungültige Produktdatenantwort.')
            return data
    except HTTPError as error:
        messages = {401: 'API-Schlüssel ungültig.', 403: 'API-Kontingent oder Zugriff nicht verfügbar.',
                    404: 'Artikel nicht gefunden.', 429: 'API-Abfragelimit erreicht. Bitte später erneut versuchen.'}
        error.close()
        raise ValueError(messages.get(error.code, 'Produktdatendienst vorübergehend nicht verfügbar.')) from error
    except (URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Produktdaten konnten nicht abgerufen werden. Die Liste bleibt unverändert.') from error


def product_url(value):
    if not isinstance(value, str):
        return ''
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ''
        if parsed.scheme in ('http', 'https') and host in ('reichelt.de', 'www.reichelt.de', 'reichelt.com', 'www.reichelt.com') and not parsed.username and not parsed.password and parsed.port in (None,80,443):
            return value
    except ValueError:
        pass
    return ''


def lookup(article, key):
    search = api_get('reichelt-search-by-keyword', {'keyword': article}, key)
    results = search.get('searchProductDetails', [])
    if not isinstance(results, list):
        raise ValueError('Ungültige Produktsuche.')
    matches = [item for item in results if isinstance(item, dict)
               and isinstance(item.get('articleNumber'), str) and article_key(item['articleNumber']) == article_key(article)]
    if len(matches) != 1:
        raise ValueError('Kein eindeutiger Treffer mit exakt dieser Reichelt-Artikelnummer. Bitte manuell prüfen.')
    ident = matches[0].get('productId')
    if not isinstance(ident, (str, int)) or not re.fullmatch(r'[0-9]+', str(ident)):
        raise ValueError('Produkt-ID fehlt in der Suchantwort.')
    data = api_get('reichelt-lookup-product', {'productId': str(ident)}, key)
    if not isinstance(data.get('articleNumber'), str) or article_key(data['articleNumber']) != article_key(article):
        raise ValueError('Artikelnummer in den Produktdetails stimmt nicht überein.')
    return describe_product(data, article)


def describe_product(data, article):
    details = data.get('productDetails', [])
    if not isinstance(details, list):
        details = []
    values = {str(item['name']).casefold(): str(item['value']) for item in details
              if isinstance(item, dict) and 'name' in item and 'value' in item}
    categories = data.get('categories', [])
    text = ' '.join(str(v) for v in categories if isinstance(v, str)).casefold() if isinstance(categories, list) else ''
    text += ' '+str(data.get('productTitle', '')).casefold()
    category = next((target for word, target in [('widerstand', 'Widerstände'), ('kondensator', 'Kondensatoren'),
                    ('kerko', 'Kondensatoren'), ('transistor', 'Transistoren'), ('diode', 'Dioden'),
                    ('logik', 'ICs'), ('schieberegister', 'ICs'), ('arduino', 'Module / Arduino')]
                     if word in text), 'Sonstiges')
    def string(name, maximum):
        value = data.get(name, '')
        return value[:maximum].strip() if isinstance(value, str) else ''
    attributes = {}
    warnings = []
    # Only unambiguous scalar values are converted to the inventory's fixed units.
    for labels, target, factors in [
        (['widerstand'], 'Widerstand', {'Ω': 1, 'Ohm': 1, 'kΩ': 1000, 'kOhm': 1000, 'MΩ': 1000000, 'MOhm': 1000000}),
        (['kapazität', 'kapazität [nf]', 'kapazität [µf]', 'kapazität [pf]'], 'Kapazität', {'pF': 0.000001, 'nF': 0.001, 'µF': 1, 'uF': 1, 'mF': 1000, 'F': 1000000}),
        (['spannung', 'spannung dc', 'nennspannung', 'spannungsfestigkeit'], 'Spannungsfestigkeit', {'V': 1, 'V=': 1, 'VDC': 1, 'mV': 0.001, 'kV': 1000}),
        (['toleranz'], 'Toleranz', {'%': 1}),
        (['nennlast', 'leistung', 'verlustleistung'], 'Leistung', {'W': 1, 'mW': 0.001, 'kW': 1000}),
        (['rastermaß'], 'Rastermaß', {'mm': 1, 'cm': 10, 'm': 1000}),
    ]:
        labels = [label.casefold() for label in labels]
        raw_values = {str(item['value']).strip() for item in details if isinstance(item,dict) and str(item.get('name','')).casefold() in labels and 'value' in item}
        if len(raw_values) > 1:
            warnings.append(target+': widersprüchliche Angaben in der technischen Tabelle; bitte manuell prüfen.')
            continue
        raw = next(iter(raw_values), '').replace('μ', 'µ').replace('Ω', 'Ω')
        if target == 'Toleranz':
            raw = raw.removeprefix('±').removeprefix('+/-').strip()
        match = re.fullmatch(r'\s*([0-9]+(?:[.,][0-9]+)?)\s*([^\s]+)\s*', raw)
        if match and match[2] in factors:
            number = float(match[1].replace(',', '.'))*factors[match[2]]
            if math.isfinite(number):
                attributes[target] = number
        if raw and target not in attributes:
            warnings.append(target+': kein eindeutiger Einzelwert ('+raw+').')
    if values.get('typ'):
        attributes['Typ'] = values['typ']
    if values.get('material'):
        attributes['Widerstandsart' if category == 'Widerstände' else 'Material'] = values['material']
    for source, target in [('ausführung', 'Ausführung'), ('spezifikation', 'Spezifikation'), ('tk', 'Temperaturkoeffizient')]:
        if values.get(source):
            attributes[target] = values[source]
    manufacturer = string('manufacturer', 200)
    return dict(name=string('productTitle', 300) or article, manufacturer='' if manufacturer == 'FREI' else manufacturer,
                mpn=string('mpn', 200), package=values.get('bauform', '')[:200],
                description=string('productDescription', 20000), product_url=product_url(data.get('url')),
                category_name=category, category_path=categories if isinstance(categories,list) else [],
                category_ids=[node['id'] for node in data.get('categoryNodes', [])
                              if isinstance(node,dict) and isinstance(node.get('id'),int)],
                suggested_attributes=attributes, warnings=warnings,
                datasheet_url=datasheet_url(data.get('datasheet_url', '')))


ATTRIBUTE_SPECS = {
    'Widerstand': ('number', 'Ω'), 'Toleranz': ('number', '%'),
    'Widerstandsart': ('text', ''), 'Typ': ('text', ''), 'Material': ('text', ''),
    'Ausführung': ('text', ''), 'Spezifikation': ('text', ''), 'Temperaturkoeffizient': ('text', ''),
    'Leistung': ('number', 'W'), 'Kapazität': ('number', 'µF'),
    'Spannungsfestigkeit': ('number', 'V'), 'Rastermaß': ('number', 'mm'),
}


def datasheet_url(value):
    if not isinstance(value, str):
        return ''
    try:
        parsed = urlparse(value)
        if parsed.scheme == 'https' and parsed.hostname in ('cdn-reichelt.de', 'www.reichelt.de', 'www.reichelt.com') and not parsed.username and not parsed.password and parsed.port in (None,443):
            return value
    except ValueError:
        pass
    return ''
