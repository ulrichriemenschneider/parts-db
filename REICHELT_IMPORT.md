# Reichelt-Listenimport und Produktdaten

Recherche vom 29.10.2026. Grundlage: `reichelt-20261029.csv`, vorhandenes partsDB-Datenmodell und die unten verlinkten Primärquellen. Der Reichelt-Importer mit Projektbedarf, Teillieferungen und optionalem everydata.io-Adapter ist inzwischen implementiert. Die folgenden Rechercheabschnitte dokumentieren die Quellenlage und den ursprünglichen Vorschlag. Aktuelle Bedienung und Konfiguration stehen in der README. Erfolgreiche Live-API-Antworten mit einem Nutzerschlüssel sind weiterhin nicht verifiziert.

## Ergebnis

Eine öffentlich dokumentierte, frei nutzbare REST-Produktdaten-API von Reichelt selbst wurde bei der Recherche nicht gefunden. Daraus folgt keine Aussage über nicht öffentliche Partnerzugänge. Offiziell bietet Reichelt OCI und BMEcat für die Beschaffung durch Firmenkunden an. Als unmittelbar dokumentierte REST-Alternative gibt es einen unabhängigen Drittanbieter. Für partsDB ist deshalb ein eigener Reichelt-Listenimport mit optionaler Produktdatenanreicherung sinnvoll.

## Tatsächliches Format der Beispieldatei

Die Datei ist 249 Bytes groß, UTF-8 mit BOM, semikolongetrennt und besitzt **keine Kopfzeile**. Sie enthält elf unterschiedliche Artikelnummern mit insgesamt 55 angeforderten Einheiten:

| Artikelnummer | Listenmenge |
| --- | ---: |
| SN 74HC595N TEX | 2 |
| STECKBOARD DBS | 1 |
| STECKBOARD 3K5V | 1 |
| KERKO 100N | 10 |
| VIS C1002FC100 | 10 |
| LED 3MM 2MA GN | 3 |
| TEX 40 | 1 |
| EVL 1224SDRC | 3 |
| EVL 204-10UYD | 3 |
| METALL 330 | 20 |
| 28C256-150 | 1 |

Beispielzeile:

```csv
"SN 74HC595N TEX";"2";""
```

Die dritte Spalte ist in allen elf Zeilen leer. Ihre genaue Bedeutung lässt sich aus dieser Datei nicht feststellen. Sie sollte bis zur Klärung unverändert als Zusatzinformation erhalten bleiben. Reichelt beschreibt für selbst erstellte Listen Artikelnummer und gewünschte Anzahl als die ersten beiden semikolongetrennten Spalten; eigene Notizen/Artikelnummern sind in der Listenoberfläche ebenfalls vorgesehen. Die Dokumentation ordnet diese jedoch keiner dritten CSV-Spalte ausdrücklich zu. [Quelle: Reichelt-Listenhilfe](https://www.reichelt.de/de/de/shop/landingpage/01%20Gr%C3%BCnde-1388)

**Ursache der bisherigen Fehlermeldungen:** Die Datei ist ein gültiger Reichelt-Listenexport, aber kein partsDB-Tabellenexport. Die erste Zeile enthält bereits einen Artikel. Ein partsDB-Import mit Pflichtkopfzeile kann sie deshalb nicht zuordnen. Nur Trennzeichen zu erkennen oder eine beliebige Kopfzeile voranzustellen reicht für eine korrekte Übernahme nicht aus.

Die Datei enthält weder lokale Datenbank-IDs noch Titel, Hersteller, Herstellerteilenummern, Kategorien, Lagerplätze, Produkt- oder Datenblattadressen.

## Verfügbare Datenzugänge

### Offiziell: Reichelt eProcurement

- **OCI:** Shop-Punchout mit Warenkorbübergabe an Beschaffungssysteme, etwa SAP. Das ist keine allgemeine Produktsuch-REST-API.
- **BMEcat:** Katalog- und Preisdaten einschließlich Bild- und Datenblattlinks; Bereitstellung etwa per E-Mail oder FTP-Push. Für die Datenanreicherung wäre dieses Katalogformat grundsätzlich geeignet.
- Reichelt verweist für diese Firmenkundenangebote auf `business@reichelt.de`. Zugang für ein privates Inventar, Bedingungen, Kosten und konkrete Felder sind öffentlich nicht geklärt; dafür wäre eine Anfrage durch den Nutzer erforderlich.

[Quelle: Reichelt eProcurement](https://www.reichelt.de/de/de/shop/landingpage/00-00%20Header-2105?r=1)

### Drittanbieter: everydata.io

Der unabhängige Anbieter dokumentiert eine REST-API für Reichelt-Produkte. Laut Anbieter: 100 kostenlose Anfragen pro Monat, danach kostenpflichtige Tarife ab 30 Euro/Monat für 5.000 Anfragen, zuzüglich Umsatzsteuer. Dies sind Anbieterangaben zum Recherchestand, keine gemessene Zuverlässigkeit. Ein eigener API-Schlüssel ist nötig. [Angebot und Preise](https://everydata.io/apis/reichelt), [Authentifizierung](https://everydata.io/docs/getting-started)

Die öffentlich abrufbare OpenAPI-Spezifikation enthält:

```text
GET https://api.everydata.io/rch/reichelt-search-by-keyword?keyword=...
GET https://api.everydata.io/rch/reichelt-lookup-product?productId=...
Header: x-api-key
```

Die Suche liefert unter anderem `articleNumber`, `productId` und `dpUrl`. Der Detailabruf dokumentiert `productTitle`, `manufacturer`, `mpn`, `productDescription`, `productDetails`, `categories` und `url`. Die Artikelnummer muss zunächst gesucht werden; `productId` ist die numerische Shop-ID und nicht die Artikelnummer aus der CSV. Ein eigenes Feld für Datenblattlinks ist im dokumentierten Detailbeispiel nicht enthalten. Das muss vor einer Zusage separat geprüft werden. [Quelle: OpenAPI-Spezifikation](https://api.everydata.io/openapi.json)

Verifiziert wurden die abrufbare Spezifikation (HTTP 200) und eine Anfrage ohne Schlüssel (HTTP 401). Erfolgreiche Produktantworten wurden mangels API-Schlüssel **nicht** getestet. Bei genau einem eindeutigen Treffer und je einem Detailabruf wären für die elf Positionen rechnerisch 22 Aufrufe nötig; erneute Suchen oder weitere Ergebnisse können zusätzliche Aufrufe erfordern.

### Alternative: direkte Produktseiten auslesen

Die Produktseiten enthalten die benötigten Informationen. Ein eigener HTML-Parser würde einen Drittanbieterzugang vermeiden, müsste aber bei Shopänderungen gepflegt werden und fehlgeschlagene Abfragen behandeln. Auch das unabhängige Projekt Part-DB verwendet für seinen Reichelt-Provider Webscraping und bezeichnet dies ausdrücklich als inoffiziell. Das ist keine offizielle Reichelt-API. [Quelle: Part-DB-Dokumentation](https://docs.part-db.de/usage/information_provider_system.html#reichelt)

## An Beispielen überprüfte Daten

Die folgenden Angaben stammen aus den verlinkten Reichelt-Produktseiten, nicht aus einer erfolgreichen Drittanbieter-API-Antwort. Die Kategorienzuordnung zu partsDB ist ein Vorschlag.

| CSV-Artikelnummer | Gefundene Produktdaten | Vorgeschlagene partsDB-Zuordnung |
| --- | --- | --- |
| SN 74HC595N TEX | Texas Instruments, Herstellerteilenummer SN74HC595N, Schieberegister, DIP-16 | Kategorie ICs; Hersteller, MPN und Bauform befüllen |
| METALL 330 | Yageo, MF0207FTE52-330R, 330 Ω, 1 %, Bauform 0207 | Kategorie Widerstände; Widerstand = 330, Toleranz = 1 |
| KERKO 100N | Keramikkondensator, 100 nF, Rastermaß 5 mm, Herstellerangabe FREI; keine konkrete MPN angegeben | Kategorie Kondensatoren; Kapazität = 0,1 µF; MPN leer lassen |

Quellen: [Schieberegister](https://www.reichelt.de/de/de/shop/produkt/schieberegister_8-bit_seriell_zu_parallel_2_6_v_dil-16-217325), [Widerstand](https://www.reichelt.de/de/de/shop/produkt/widerstand_metallschicht_330_ohm_0207_0_6_w_1_-11733), [Kondensator](https://www.reichelt.de/de/de/shop/produkt/keramik-kondensator_100_nf_-20_80_y5v_50_100_v_rm_5-9265)

Beim Kondensator weichen die Spannungsangaben innerhalb der Produktseite voneinander ab: Titel/Beschreibung nennen 50/100 V, die technische Tabelle 50 V. Solche Angaben sollten in der Vorschau zur Prüfung markiert werden. Der Eintrag FREI identifiziert keinen eindeutigen Bauteilhersteller. Ein Datenblattlink ist auf dieser Produktseite vorhanden: [Reichelt-Datenblatt](https://cdn-reichelt.de/documents/datenblatt/B300/kerko.pdf).

## Vorgeschlagener Ablauf für partsDB

1. Eigenen Importtyp „Reichelt-Liste“ anbieten und die Datei ohne Kopfzeile lesen. Die erste Position muss erhalten bleiben. Artikelnummer und positive ganzzahlige Menge prüfen; zusätzliche Inhalte nicht stillschweigend verwerfen.
2. Den Lieferanten Reichelt zentral zuordnen. Artikelnummern ausschließlich als `Offer.article_number` behandeln, niemals als `Part.id` oder Herstellerteilenummer. Bei wiederholten Imports über Lieferant und Artikelnummer nach vorhandenen Angeboten suchen; Mehrdeutigkeiten anzeigen.
3. Stammdaten optional über einen austauschbaren Datenanbieter ergänzen. Suchtreffer anhand der vollständigen Artikelnummer abgleichen; ähnliche Artikel oder andere Bauformen nicht automatisch übernehmen. Bereits bekannte Produkt-IDs/Links zwischenspeichern.
4. Titel, Hersteller, MPN, Bauform und Links den vorhandenen Feldern zuordnen. Technische Werte auf die festen Kategorieeinheiten umrechnen, etwa 100 nF → 0,1 µF. Unbekannte Merkmale und widersprüchliche Werte zur Prüfung anzeigen. Preis und EAN besitzen aktuell keine eigenen Modellfelder und sind für den ersten Import nicht erforderlich.
5. Vorschau mit neu/vorhanden/unklar, Quelle und Listenmenge anzeigen. Vorhandene manuell gepflegte Werte nicht ungefragt überschreiben. Ohne Datenanbieter bleiben Artikelnummer und Listenmenge nutzbar; Beschreibung und Kategorie benötigen dann manuelle Ergänzung.
6. **Projektbedarf und Bestand getrennt behandeln.** Nach Nutzerbeschreibung sind dies Planungslisten. Daher standardmäßig Bauteile/Angebote übernehmen und Mengen als Bedarf/Importinformation erhalten, ohne Zugang zu buchen. Das jetzige Datenmodell hat keine eigene Projektbedarfstabelle. Für dauerhaft strukturierte Projektlisten wäre eine Erweiterung nötig; eine einfache erste Variante kann die Listenmenge mit Herkunft in einer Notiz erhalten. Eine echte Einlagerung benötigt ausdrücklich einen Lagerplatz und eine bestätigte Mengenbuchung.
7. Erst die bestätigte Vorschau transaktional übernehmen. Importdatei und Inventarzustand wie bisher binden. Netzwerkfehler dürfen keinen Teilimport auslösen; Produktdaten werden vor der endgültigen Datenbanktransaktion abgerufen.

## Empfehlung und noch zu klären

Zuerst den direkten Reichelt-Listenimport ergänzen. Die Dateierkennung und Vorschau sollten ohne externen Dienst funktionieren. Produktdatenanreicherung danach optional ergänzen: BMEcat, falls Reichelt einen passenden Zugang anbietet; andernfalls einen kleinen Test mit everydata.io durchführen oder einen eigenen Reichelt-Parser pflegen. Für den API-Test fehlen ein Nutzerschlüssel und die Prüfung realer Antworten insbesondere auf exakte Artikelzuordnung und Datenblattlinks.

Es wurden keine Konten registriert, keine kostenpflichtigen Leistungen gebucht, keine Nachrichten an Anbieter versendet und keine Inventardaten verändert.


## Umgesetzt nach Freigabe

- Automatische Erkennung der Originaldatei im CSV-Import und eigener Menüpunkt Projektbedarf.
- Stufenweise Vorschau/Übernahme; Projektname sowie neue Bezeichnungen und Kategorien sind änderbar.
- Eigene Tabellen für Projektlisten und Positionen mit geplant/erhalten; zusätzliche Buchungskennungen verhindern doppelte Wareneingänge bei Netzwerk-Wiederholungen.
- Auswahl einzelner Positionen, Mengenänderung bis zum offenen Bedarf, gemeinsamer oder individueller Lagerplatz und spätere Teilwareneingänge.
- Optionale Produktvorschläge pro neuer Position über `REICHELT_API_KEY`; keine externen Anfragen allein durch den Dateiimport. Vorhandene Bauteile bleiben unverändert.
- SQLite-Migration `0002`, Integrations- und MCP-Browsertests mit separaten Testdatenbanken. Echte externe API-Antworten bleiben mangels Nutzerschlüssel ungeprüft; der konfigurierte Ablauf wird mit lokalen Testantworten geprüft.


## Nachträgliche Vervollständigung in Projektlisten

Seit der Erweiterung um Migration `0003` bietet jede bestehende Projektposition „Daten vervollständigen“. Ein regulärer Chromium-Browser liest die deutsche Produktsuche und die exakt passende Produktseite aus. Die Datenübernahme erfolgt aus einer separaten Vorschau; vorhandene Werte und Einheiten bleiben ohne ausdrückliche Auswahl erhalten. Typ, Widerstandsart, Leistung und weitere erkannte Merkmale werden strukturiert gespeichert. Quelle, Abrufzeit, 24-Stunden-Cache und Fehlerhinweise sind Teil des Ablaufs. Ein kompletter Live-Browserablauf für METALL 330 wurde auf einer separaten Testdatenbank erfolgreich geprüft. Das betrifft den eigenen Browser-Scraper; der everydata.io-Adapter wurde weiterhin nicht mit einem echten Nutzerschlüssel getestet.

Das vom Nutzer genannte [ReicheltAPI-Repository](https://github.com/jkreucher/ReicheltAPI) und dessen [Quelltext](https://github.com/jkreucher/ReicheltAPI/blob/main/reichelt.py) wurden geprüft. Es nutzt requests/BeautifulSoup und dokumentiert technische Tabellen, Kategorien sowie Datenblattlinks. Wir verwenden es als fachliche Referenz, ohne eine zusätzliche Bibliotheksabhängigkeit oder Quelltextübernahme. Die eigene Browserauswertung basiert auf der aktuellen live inspizierten Produktseite; direkte HTTP-Anfragen wurden durch eine Reichelt-Schutzseite beantwortet.
