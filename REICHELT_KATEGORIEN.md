# Reichelt-Kategorien – Stand 29.10.2026

Die Anwendung übernimmt **2.783 Kategorien mit Reichelt-ID, Originalbezeichnung, vollständigem Pfad, Elternkategorie und Quelladresse**. Es handelt sich um einen lokal gespeicherten Stand der öffentlich erreichbaren deutschen Shop-Kategorien. Die App benötigt zum Anzeigen des Kategorienbaums keine Netzwerkverbindung.

## Quellen und Vollständigkeitsprüfung

- [Reichelt-Shop und Hauptnavigation](https://www.reichelt.de/de/de/).
- [Offizieller Sitemap-Index](https://www.reichelt.de/sitemap.xml), über die [robots.txt](https://www.reichelt.de/robots.txt) veröffentlicht.
- Sämtliche **13 Kategorie-Sitemaps** `https://www.reichelt.de/sitemaps/categories/category_0.xml` bis `category_12.xml` mit zusammen **1.935 unterschiedlichen Kategorie-IDs**.
- Zusätzlich die Kategorien aus allen zehn Hauptgruppen der Shop-Navigation und deren Untergruppen, insbesondere [Bauelemente](https://www.reichelt.de/de/de/shop/kategorie/bauelemente-2875), die im Sitemap-Index nicht als eigener Baum aufgeführt sind.
- **519 Gruppenseiten** wurden seriell mit regulärem Chromium gelesen. Die Kategorieüberschriften, Untergruppen und Breadcrumbs liefern Originalbezeichnungen und Elternbeziehungen. Es wurden keine Produktlisten vollständig abgerufen und keine Schutzabfragen umgangen.

Alle Sitemap-IDs sind enthalten, alle gefundenen Untergruppen vollständig abgearbeitet. Jeder Elternknoten existiert; die Pfade sind kreisfrei und eindeutig. Die Sitemaps führen auch zusätzliche Bereiche wie „Katalog“, „Katalog Plus“ und „Gruppe unsichtbar“ auf. Diese öffentlich veröffentlichten Kategorien bleiben im übernommenen Stand enthalten.

Der eingefrorene Datensatz [reichelt_categories_20261029.json](backend/data/reichelt_categories_20261029.json) dokumentiert die Kategorien, sämtliche Sitemap-IDs, Quellen und geprüften Gruppenseiten. Gleichlautende Namen in verschiedenen Bereichen bleiben separate Kategorien. Zwei „Programmer / Entwicklungstools“-Einträge besitzen sogar denselben sichtbaren Elternpfad; ihr gespeicherter Pfad enthält deshalb zusätzlich die jeweilige Reichelt-ID.

## Austausch vorhandener Kategorien

Migration `0006` entfernt die bisherigen Kategorien aus dem aktiven Katalog und installiert den recherchierten Stand. Bereits gespeicherte Bauteile behalten ihre IDs, Stammdaten, Angebote, Bestände, Projektverweise und Pflegestände. Ihre Kategorie wird anhand vorhandener, exakt zugeordneter Reichelt-Produktdaten auf den passenden Pfad gesetzt. Ohne solche Daten werden bisherige Fachkategorien auf die entsprechende Reichelt-Gruppe abgebildet; bislang nicht klassifizierte oder eigene Alt-Kategorien landen zunächst in **Bauelemente**. Eine spätere Datenvervollständigung bietet die genauere Unterkategorie an.

Vorhandene Merkmale werden in die Zielkategorie übernommen. Bei einem echten Einheiten-/Typkonflikt bleibt der alte Zahlenwert mit seiner alten Definition unter einem gekennzeichneten Merkmalsnamen erhalten, beispielsweise `Widerstand [bisher: Widerstände, kΩ]`. Er wird niemals ungefragt von kΩ nach Ω umgedeutet. Abgelaufene Import- und Produktvorschauen werden beim Austausch verworfen, weil sie alte Kategorie-IDs enthalten können.

Vor der lokalen Übernahme wurde ein vollständiges SQLite-Backup erstellt. Eine Rücknahme des Datenaustauschs erfolgt über dieses Backup; Alembic-Downgrade ist für diese Datenmigration bewusst nicht vorgesehen.

## Bedienung und Datenaustausch

Unter **Kategorien** lassen sich Untergruppen öffnen und vollständige Pfade durchsuchen. Die Ergebnisliste hat eine Seitennavigation. Kategorieauswahlen in Filtern, Bauteilformularen und Projektimporten lassen sich über ein Suchfeld eingrenzen. Eine bereits getroffene Auswahl bleibt dabei erhalten. Ein Oberkategorienfilter umfasst alle Unterkategorien; technische Zahlenfilter berücksichtigen nur dieselbe Merkmalsdefinition und Einheit.

Reichelt-Pfade bleiben fest, technische Merkmale können bearbeitet und eigene zusätzliche Kategorien weiterhin angelegt werden. Neue Reichelt-Produktdaten werden vorrangig anhand der Kategorie-IDs des Breadcrumbs zugeordnet, nicht anhand einer geratenen Namensliste.

Die Spalten von `categories.csv` bleiben `id,name,fields`; `name` enthält nun den eindeutigen vollständigen Pfad. Reichelt-ID, Elternbeziehung und Quellen stehen in einer separaten Metadatentabelle. Sie sind im vollständigen Datenbankbackup enthalten. Ein CSV-Inventarexport ersetzt daher weiterhin kein vollständiges Backup.

## Erneut recherchieren

```bash
node scripts/fetch_reichelt_categories.mjs /tmp/reichelt-kategorien-neu.json
.venv/bin/python scripts/freeze_reichelt_categories.py \
  /tmp/reichelt-kategorien-neu.json /tmp/reichelt-kategorien-stand.json
```

Der Abruf ist fortsetzbar, verwendet öffentliche Kategorie-Seiten und pausiert zwischen Anfragen. Bei Sperren oder fehlenden Pfaden wird abgebrochen; ein unvollständiger Stand lässt sich nicht einfrieren. Einen künftigen Stand als neue Datendatei mit eigener Migration übernehmen. Den von Migration `0006` referenzierten Stand nicht nachträglich verändern.

## Prüfung

66 Integrationstests prüfen unter anderem den vollständigen Datenbestand, Elternbeziehungen, gleiche Namen, Zuordnung über Breadcrumbs, Filter über Unterkategorien, Schutz fester Einheiten sowie die Migration vorhandener Bauteile. Zwölf Playwright-MCP-Szenarien mit separater Testdatenbank decken außerdem Kategorienavigation, Suche, Auswahl, gespeicherte Unterkategorie und Desktop-/Mobilansichten ab.
