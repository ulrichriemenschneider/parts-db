# partsDB

Persönliche Bauteilverwaltung mit Flask, SQLAlchemy, SQLite und Vite (JavaScript). Funktionsumfang und Entscheidungen stehen in [PROJEKTPLAN.md](PROJEKTPLAN.md).

## Lokal starten

Voraussetzungen: Python ab 3.11, Node.js ab 22.12 und npm.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
cp .env.example .env
chmod 600 .env
.venv/bin/flask --app backend.app migrate
.venv/bin/flask --app backend.app set-user
npm --prefix frontend ci
.venv/bin/flask --app backend.app run --host 127.0.0.1
```

In einem zweiten Terminal:

```bash
npm --prefix frontend run dev
```

Die von Vite ausgegebene lokale URL öffnen. Vite leitet `/api` an Flask weiter. Die lokale `.env` enthält `COOKIE_SECURE=0` für HTTP und `TRUST_PROXY=0`. Für HTTPS `COOKIE_SECURE=1` verwenden. Bei einer vorhandenen `.env` die Einstellungen ergänzen, statt die Datei zu überschreiben. Das Passwort wird verdeckt abgefragt und muss mindestens zwölf Zeichen haben. Standarddatenbank: `instance/parts.sqlite`.

Das Backend liest die `.env` im Projektverzeichnis auch bei Gunicorn-Starts ein. Bereits gesetzte Umgebungsvariablen haben Vorrang; nach einer Konfigurationsänderung das Backend neu starten. `.env.example` dokumentiert die Optionen für Datenbank, Sicherungsverzeichnis und Reichelt-Zugriff ohne Geheimnisse. Benutzername und Passwort-Hash bleiben in der Datenbank; ein Klartextpasswort wird weder in `.env` noch im Frontend hinterlegt. Ein neuer Klon enthält kein vorkonfiguriertes Konto: `migrate` und `set-user` richten es lokal ein.

## Konto ändern und Datenbank zurücksetzen

Unter **Einstellungen → Benutzername und Passwort** lassen sich die Zugangsdaten mit dem aktuellen Passwort ändern. Ein leeres neues Passwort lässt das bisherige bestehen; ein neues Passwort benötigt mindestens zwölf Zeichen und eine Wiederholung. Speichern beendet alle Sitzungen. Anschließend mit den geänderten Daten anmelden. Bei vergessenem Passwort bleibt `flask --app backend.app set-user` als lokaler Wiederherstellungsweg verfügbar. Die CLI-Option `--allow-short-password` erlaubt ausdrücklich ein kurzes Anfangspasswort ab vier Zeichen für die lokale Einrichtung; die App verlangt bei späteren Passwortänderungen weiterhin zwölf Zeichen.

Unter **Einstellungen → Datenbank zurücksetzen** zeigt eine Vorschau die betroffenen Datensätze. Gelöscht werden Bauteile, Bestände, Lieferantenangebote, Projektlisten einschließlich Positionen und Wareneingängen, Lagerplätze, Lieferanten, Pflegestatus und Produktcache. **Alle Kategorien einschließlich eigener Kategorien, Hierarchie, technischer Merkmale und Einheiten sowie das Konto bleiben erhalten.** Auch Anmeldesitzungen, frühere Importvorschauen und Abrufzustände werden zurückgesetzt.

Zum Ausführen das aktuelle Passwort und `ZURÜCKSETZEN` eingeben. Vor dem Löschen wird eine konsistente vollständige SQLite-Sicherung mit Integritätsprüfung und Dateirechten 600 erstellt. Standardverzeichnis: `instance/backups`, mit `PARTSDB_BACKUP_DIR` änderbar. Scheitert die Sicherung, wird nichts gelöscht. Bei zwischenzeitlich geänderten Daten oder nach zehn Minuten muss die Vorschau erneut geöffnet werden. Ein laufender Reichelt-Abruf muss zunächst beendet werden. Nach dem Reset erneut mit den bisherigen Zugangsdaten anmelden. Sicherungen enthalten auch Kontodaten und gehören außerhalb des Repositorys aufbewahrt; Wiederherstellung siehe unten.

Alternativ in der passenden Backend-Umgebung:

```bash
.venv/bin/flask --app backend.app reset-data
```

Der Befehl fragt vor dem Löschen nach und erstellt dieselbe automatische Sicherung. `--yes` bestätigt die Löschung ausdrücklich für Skripte. Er erhält Kategorien und Konto ebenfalls.

## Auf GitHub veröffentlichen

Ein Datenbankreset ist dafür nicht nötig. `.gitignore` schließt lokale `.env`-Dateien, Datenbanken, `instance/` einschließlich Sicherungen, Logs und erzeugte Abhängigkeiten/Builds aus. `.env.example`, `deploy/partsdb.env.example`, Migrationen und der recherchierte Kategorienkatalog sind zur Weitergabe vorgesehen. Zugangsdaten werden auf jedem Rechner mit `set-user` eingerichtet. Der Passwort-Hash bleibt ausschließlich in der privaten Datenbank.

Vor dem ersten Push die tatsächlich vorgemerkten Dateien und eine gegebenenfalls vorhandene Git-Historie prüfen: `.gitignore` entfernt keine bereits versionierten Dateien. Bereits veröffentlichte Geheimnisse müssen ersetzt und aus der Historie entfernt werden; siehe [GitHub-Anleitung](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). In dieser Arbeitsumgebung ist `.git` ein leerer Platzhalter; versionierte Dateien und Historie konnten deshalb nicht geprüft werden. Es wurde nichts auf GitHub hochgeladen.

## Tests und Build

```bash
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend run build
```

Die Integrationstests nutzen temporäre Datenbanken und die echten Alembic-Migrationen. Der vollständige Browserablauf lässt sich zusätzlich über den offiziellen Playwright-MCP-Server prüfen:

```bash
.venv/bin/python tests/run_browser_tests.py --chromium /usr/bin/chromium
```

Den Pfad bei Bedarf an den installierten Chromium/Chrome anpassen. Der MCP-Server ist als Entwicklungsabhängigkeit in `frontend/package-lock.json` fixiert und wird mit `npm --prefix frontend ci` installiert. Der Test startet Flask, Vite und Playwright MCP selbst, verwendet freie lokale Ports und eine **neue, separate SQLite-Testdatenbank unter `/tmp/partsdb-browser-*`**. Die Standarddatenbank `instance/parts.sqlite` bleibt unberührt. Alle Testprozesse werden abschließend beendet; Datenbank, JSON-Ergebnisse, Serverlogs und Desktop-/Mobil-Screenshots bleiben im ausgegebenen temporären Verzeichnis zur Prüfung erhalten. Lieferantenziele werden im Testbrowser lokal beantwortet, sämtliche Anwendungs- und API-Anfragen laufen gegen die echte Anwendung.

Die zwölf Browser-Szenarien prüfen Anmeldung/Abmeldung, Stammdaten und Hierarchie, Bauteile und technische Werte, alle Bestandsaktionen samt Fehlerfällen, Suche/Filter/Sortierung/Seitennavigation, Lieferantenangebote und Links, Referenzschutz, CSV-Download/-Vorschau/-Übernahme/-Rollback sowie den Schutz vor veralteten Vorschauen. Dazu gehören Reichelt-Neuanlage über Herstellerteilenummer und Artikelnummer mit Vorschau, Abbrechen, Duplikaterkennung und Öffnen über den Artikelnamen. Der Projektablauf importiert die originale Reichelt-Beispieldatei als Projektbedarf, bucht ausgewählte Teilmengen auf unterschiedliche Lagerplätze und prüft Wiederholungen, konkurrierende Tabs und Restmengen. Zusätzlich werden die Änderung beider Zugangsdaten mit erneuter Anmeldung, Reset-Abbruch, die Passwort-/Bestätigungsabfrage, automatische Sicherung und der vollständige Reset mit Erhalt aller Kategorien geprüft. Die mobile Bedienung und die Datenbankintegrität werden ebenfalls geprüft.

Mit `.venv/bin/python tests/run_browser_tests.py --chromium /usr/bin/chromium --enrichment-fixture` wird außerdem die optionale Produktdatenanreicherung über eine lokale Testantwort geprüft. Beide Varianten senden keine Anfragen an einen echten Produktdatenanbieter. `node tests/test_scraper.mjs` prüft zusätzlich den Browser-Parser gegen eine lokale HTML-Testdatei. Mit `--live-scraper` können ausdrücklich echte Reichelt-Abrufe bei der Bauteilanlage und im Projektlisten-Ablauf geprüft werden; die Testdatenbank bleibt auch dabei separat.

`frontend/dist` enthält den Produktionsbuild. `frontend/package-lock.json` fixiert die npm-Abhängigkeiten. `requirements-lock.txt` hält die geprüften Python-Versionen fest; `requirements.txt` beschreibt die erlaubten Versionsbereiche. Für eine Installation mit dem geprüften Stand die Lockdateien wie oben verwenden.

## Bedienung

1. Lagerplätze und Lieferanten anlegen; Kategorien und technische Merkmale bei Bedarf ergänzen.
2. Bauteil anlegen, technische Werte in den angegebenen festen Einheiten erfassen.
3. In den Bauteildetails Zugang, Entnahme, Korrektur oder Umlagerung ausführen.
4. Lieferantenartikel mit Produkt- und Datenblattlinks hinzufügen.
5. Bauteile über Text, Kategorie, Lagerplatz, Bestand und Merkmal finden.

Alle Bestände sind Stückzahlen. Lagerplatzfilter beziehen sich auf den ausgewählten Platz, nicht automatisch auf seine Unterplätze. Eine Zeile mit Menge null kann erhalten bleiben; referenzierte Lagerplätze werden deshalb auch dann nicht gelöscht. Ein versehentliches Bauteil kann nach Bestätigung mit seinen Beständen entfernt werden.

**Projektbedarf, Lagerplätze und Lieferanten** verwenden ebenfalls eine Tabellenansicht mit Suche und 25 Einträgen pro Seite. Bei Projektlisten stehen Quelle, Status, Positionen, Wareneingangsstand und Importdatum in eigenen Spalten. Lagerplätze zeigen den übergeordneten Platz und die Anzahl direkter Unterplätze. Ein Klick auf den Namen öffnet die Bedarfsliste beziehungsweise das Bearbeitungsformular. Nach dem Bearbeiten bleiben Suchbegriff und aktuelle Seite erhalten; beim Löschen des letzten Eintrags einer Seite wird die Seitennummer angepasst. Lange Angaben werden umgebrochen und auf kleinen Bildschirmen je Eintrag untereinander angezeigt.

## Kategorien aus dem Reichelt-Katalog

Die bisherigen Kategorien sind durch **2.783 Reichelt-Kategorien** mit vollständigen Pfaden und Untergruppen ersetzt (Stand 29.10.2026). Unter **Kategorien** werden die Einträge wie die Bauteile als Liste mit 25 Einträgen pro Seite angezeigt: Name/Pfad, Quelle, Anzahl technischer Merkmale, Unterkategorien und Bearbeiten. Ein Klick auf den Namen öffnet die Unterkategorien beziehungsweise bei einer Kategorie ohne Untergruppen das Bearbeitungsformular. Die Suche und Navigation durch den Baum bleiben verfügbar. In den Bauteilformularen, Filtern und Projektimporten kann das Feld **Kategorien eingrenzen** die Auswahl verkürzen. Eine bereits gewählte Kategorie bleibt dabei erhalten. Ein Filter auf eine Oberkategorie findet auch Bauteile in ihren Unterkategorien.

In der Bauteilliste werden lange Kategoriepfade, Hersteller und Teilenummern umgebrochen. Die Spalten bleiben innerhalb der verfügbaren Breite; auf schmaleren Bildschirmen stehen die Angaben je Artikel untereinander. Der vollständige Kategoriepfad und die Öffnen-Aktion bleiben dabei erreichbar.

Reichelt-Pfade bleiben fest; technische Merkmale können bearbeitet und eigene Kategorien zusätzlich angelegt werden. Vorhandene Bauteile werden bei Migration `0006` anhand bereits gespeicherter Reichelt-Daten oder ihrer bisherigen Fachgruppe zugeordnet. Noch nicht klassifizierte Bauteile stehen zunächst unter **Bauelemente** und können später vervollständigt werden. Stammdaten, technische Werte, Bestände und Projektverweise bleiben erhalten. Vor dem lokalen Austausch wird ein vollständiges SQLite-Backup erstellt. Die Rücknahme erfolgt über dieses Backup.

Das CSV-Format bleibt gleich; `categories.csv` enthält im Feld `name` jetzt den vollständigen eindeutigen Pfad. Die separaten Hierarchie- und Quellenmetadaten sind im Datenbankbackup enthalten. **[Recherche, Quellen, Vollständigkeitsprüfung und Aktualisierung](REICHELT_KATEGORIEN.md)**.

## Bauteil mit Reichelt-Daten anlegen

Unter **Bauteile → Bauteil anlegen** steht oberhalb des manuellen Formulars **Mit Reichelt-Daten anlegen**. Eine Reichelt-Artikelnummer (z. B. `METALL 330`) oder Herstellerteilenummer (z. B. `MF0207FTE52-330R`) eingeben und **Produktdaten abrufen** wählen. Die Nummernart wird automatisch erkannt. Die Artikelnummer oder Herstellerteilenummer wird auf der Produktseite exakt abgeglichen. Bei mehreren nicht eindeutig zugeordneten Suchtreffern die Reichelt-Artikelnummer verwenden.

Die Vorschau zeigt die Quelle, die erkannte Kategorie sowie bearbeitbare Angaben und technische Merkmale in den festen Kategorieeinheiten. Erst **Bauteil aus Reichelt-Daten anlegen** speichert Bauteil und Lieferantenangebot mit Artikelnummer, Produktlink und gegebenenfalls Datenblatt. Beim Abbrechen wird kein Bauteil angelegt. Vorhandene Reichelt-Angebote werden erkannt und bieten das Öffnen des vorhandenen Bauteils an. Die Anlage bucht keinen Bestand; ein Zugang kann anschließend in den Bauteildetails erfasst werden.

Neue Bauteile erhalten das grüne R. Eigene Änderungen an der Vorschau setzen zusätzlich den orangen Haken; **Daten von mir vollständig geprüft** setzt den grünen Haken. In der Bestandsliste öffnet auch ein Klick auf den Artikelnamen die Bauteildetails.

Der Abruf verwendet denselben optionalen Browser-Scraper und 24-Stunden-Cache wie die Projektvervollständigung. Kein API-Schlüssel erforderlich. Kategorieeinheiten bleiben erhalten; widersprüchliche Definitionen werden als Hinweis angezeigt und betroffene Werte nicht vorausgefüllt. Migration `0005` ergänzt die sitzungsgebundene Vorschau. Die bestätigte Anlage ist atomar und gegen doppelte Speicherung geschützt.

## CSV-Format

Der Import nimmt eine einzelne **CSV-Datei** entgegen. Die Tabelle wird anhand der Kopfzeile automatisch erkannt; der Dateiname ist frei wählbar. Es gelten die unten aufgeführten Spalten in genau dieser Reihenfolge. Der Export liefert weiterhin ein ZIP mit allen sechs CSV-Dateien. CSV: UTF-8 (auch mit BOM), Kopfzeile erforderlich, Standard-CSV-Quoting. Der Export verwendet Kommas; beim Import werden Komma, Semikolon und Tabulator automatisch erkannt. Eine vorangestellte Excel-Zeile wie `sep=;` wird ebenfalls unterstützt. Anführungszeichen innerhalb eines quotierten Felds werden verdoppelt, z. B. `"Bauteil ""A"""` für `Bauteil "A"`. Bei fehlerhaften Daten nennt die Meldung die betroffene physische CSV-Zeile. IDs sind positive ganze Zahlen, optionale `parent_id` darf leer bleiben. JSON-Werte stehen als korrekt quotierte CSV-Zellen in den entsprechenden Spalten.

| Datei | Spalten in dieser Reihenfolge |
| --- | --- |
| `categories.csv` | `id,name,fields` |
| `locations.csv` | `id,name,parent_id` |
| `suppliers.csv` | `id,name` |
| `parts.csv` | `id,name,category_id,manufacturer,mpn,package,description,notes,attributes` |
| `offers.csv` | `id,part_id,supplier_id,article_number,product_url,datasheet_url` |
| `stocks.csv` | `id,part_id,location_id,quantity` |

`fields`: z. B. `[{"name":"Widerstand","type":"number","unit":"Ω"}]`. `attributes`: z. B. `{"Widerstand":10000}`. Leere Merkmalsdefinitionen sind `[]`, leere Merkmalswerte `{}`. Eine einzelne, aus dem Export entpackte CSV-Datei ist die einfachste Importvorlage. Benötigte Kategorien, Lagerplätze, Lieferanten und Bauteile müssen für referenzierte IDs bereits vorhanden sein. Für ein neues Inventar daher in Tabellenreihenfolge importieren: Kategorien → Lagerplätze → Lieferanten → Bauteile → Angebote → Bestände. Jede CSV-Datei wird einzeln geprüft und übernommen. Die API akzeptiert vorhandene vollständige ZIP-Exporte weiterhin. Gleiche IDs werden aktualisiert; **IDs aus fremden Inventaren können bestehende Daten überschreiben**. Vor dem Übernehmen die Vorschau prüfen. Der Import löscht keine Zeilen. Maximal 8 MB je CSV-Datei oder ZIP-Upload; bei ZIP maximal 32 MB entpackter Inhalt.

## Reichelt-Projektbedarf und Wareneingang

Unter **Projektbedarf → Reichelt-Liste importieren** die Original-CSV aus „Meine Listen“ hochladen und einen Projektnamen vergeben. Alternativ erkennt **Import / Export** Reichelt-Listen automatisch. Die Liste benötigt keine Kopfzeile: `"ARTIKELNUMMER";"MENGE";"optionaler Zusatz"`. UTF-8 mit/ohne BOM, eine optionale `sep=;`-Zeile und Exporte mit nur zwei Spalten werden unterstützt. Doppelte Artikelnummern werden zusammengefasst; Zusätze bleiben erhalten. Maximal 1000 unterschiedliche Positionen pro Liste.

Die Vorschau zeigt neue/vorhandene Bauteile, Menge, Bezeichnung und Kategorie. Neue Bezeichnungen und Kategorien lassen sich dort ändern. **Als Projektbedarf übernehmen** speichert die Liste und legt bei Bedarf Bauteile sowie Angebote beim Lieferanten Reichelt an. Bereits bekannte Artikel werden anhand von Lieferant und Artikelnummer wiederverwendet; vorhandene Bauteildaten bleiben erhalten. Der Import verändert keine Bestände. Dieselbe Datei unter demselben Projektnamen wird nicht doppelt importiert. Eine Vorschau gilt 30 Minuten und muss bei Änderungen an den zugehörigen Stammdaten erneut erstellt werden.

In der Projektübersicht öffnet auch ein Klick auf den **Listennamen** die Bedarfsliste. In der geöffneten Liste lässt sich über **Name ändern** der Listenname bearbeiten und mit **Namen speichern** übernehmen. **Abbrechen** behält den bisherigen Namen. Der neue Name bleibt nach dem Neuladen erhalten und erscheint auch in der Listenübersicht. Bereits vorbereitete Wareneingangsmengen, ausgewählte Positionen und Lagerplätze bleiben beim Umbenennen erhalten; bei zwischenzeitlichen Änderungen durch einen anderen Tab wird die Liste neu geladen.

In einer Projektliste stehen **geplant, erhalten und offen** je Position. Für einen späteren Wareneingang:

1. Gelieferte Positionen an- oder abwählen; „Alle offenen auswählen“ und „Auswahl aufheben“ helfen bei größeren Listen.
2. Die tatsächlich erhaltene Menge eintragen, mindestens 1 und höchstens die noch offene Menge.
3. Einen gemeinsamen Lagerplatz auswählen oder je Position einen anderen Lagerplatz angeben.
4. Auswahl und Mengen prüfen und **Wareneingang verbindlich buchen** drücken.

Teilwareneingänge sind möglich; beim nächsten Öffnen werden die verbleibenden Mengen vorgeschlagen. Erst die Buchung erhöht Bestände. Alle ausgewählten Positionen werden atomar gebucht. Eine wiederholte HTTP-Anfrage mit derselben Buchungskennung erhöht den Bestand nicht erneut. Eine seit dem Öffnen veränderte Liste muss neu geladen werden. Vollständig erhaltene Positionen werden nicht mehr zur Buchung angeboten.

Eine Bedarfsliste kann nach Bestätigung gelöscht werden; Bauteile und bereits gebuchte Bestände bleiben bestehen. Solange eine Projektposition auf ein Bauteil verweist, ist dessen Löschung gesperrt. Die neuen Tabellen werden durch Migration `0002` angelegt, ohne Konten und Inventar zu verändern. **Das vollständige SQLite-Backup enthält auch Projektlisten und Buchungskennungen. Der CSV-ZIP-Inventarexport enthält weiterhin nur die sechs Inventartabellen, keine Projektlisten.**

### Pflegestand und Anzeige in Projektlisten

Projektlisten und Bauteildialoge bleiben auf die Bildschirmbreite begrenzt. Lange Bezeichnungen, Beschreibungen, Merkmale und Notizen werden umgebrochen. Auf kleinen Bildschirmen erscheinen die Projektpositionen untereinander, sodass Mengen und Aktionen erreichbar bleiben.

Direkt hinter dem Artikelnamen stehen die gespeicherten Kennzeichen:

- **Grünes R:** Reichelt-Daten wurden bestätigt übernommen oder mit einer passenden Produktseite abgeglichen. Das Zeichen behauptet nicht, dass alle denkbaren Angaben vorhanden sind.
- **Oranger Haken:** manuell teilweise gepflegt. Er entsteht beim manuellen Speichern von Bauteildaten oder Lieferantenlinks sowie bei eigenen Änderungen an neuen Bezeichnungen/Kategorien während des Projektimports.
- **Grüner Haken:** ausdrücklich als vollständig manuell geprüft markiert. Dafür im Bauteil-Bearbeitungsformular **Daten von mir vollständig geprüft** aktivieren und speichern. Ohne Haken wird dort als teilweise gepflegt gespeichert.

Herkunft und manueller Pflegestand sind unabhängig: Ein grünes R kann zusammen mit einem manuellen Haken angezeigt werden. Die Kennzeichen gelten für das verknüpfte Bauteil in allen Projekten und bleiben nach Neuladen erhalten. Unverändertes Öffnen oder eine abgebrochene Reichelt-Vorschau setzen kein Kennzeichen.

Für ältere Datensätze ist die frühere Herkunft nicht zuverlässig gespeichert. Diese werden nicht nachträglich geraten. Ein erneuter Reichelt-Abgleich kann auch ohne Datenänderungen über **Reichelt-Abgleich bestätigen** gekennzeichnet werden. Die neue Metadatentabelle wird mit Migration `0004` angelegt. SQLite-Backups enthalten den Pflegestand; das bisherige Inventar-CSV-Format bleibt unverändert und exportiert diese Metadaten nicht.

### Informationen in einer bestehenden Projektliste vervollständigen

Mit **Alle Daten vervollständigen** werden alle Positionen der geöffneten Liste automatisch nacheinander bearbeitet, auch bereits vollständig erhaltene Positionen. Die Daten werden direkt gespeichert, ohne Einzelvorschau oder Bestätigungsdialog. Fehlende Angaben, noch als Artikelnummer benannte Bauteile und bislang unklassifizierte Kategorien werden ergänzt; bereits gepflegte Werte und eigene Notizen bleiben erhalten. Erfolgreich abgeglichene Artikel erhalten das grüne R. Die bisherige **Daten vervollständigen**-Funktion je Artikel bleibt zusätzlich verfügbar, wenn Werte bewusst verglichen oder ersetzt werden sollen.

Fortschritt und **Ergebnisse und Hinweise** zeigen erfolgreiche Positionen, Warnungen und Fehler. Nicht gefundene Artikel werden protokolliert; danach wird die nächste Position bearbeitet. Kurze Abrufpausen werden automatisch abgewartet. Bei einer Reichelt-Sperre wird der Lauf gestoppt. **Stoppen** beendet den Lauf nach dem gerade bearbeiteten Artikel; bereits gespeicherte Ergänzungen bleiben erhalten. Die Liste während des Laufs geöffnet lassen: Beim Verlassen werden nach der laufenden Position keine weiteren Positionen gestartet. Ein erneuter Start kann den vorhandenen Produktcache nutzen.

Vorbereitete Wareneingangsmengen, Auswahl und Lagerplätze bleiben im Formular erhalten. Der Sammellauf bucht keine Bestände und ändert keine Bedarfsmengen. Änderungen am Bauteil sind auch in anderen verknüpften Projekten sichtbar. Eine während des Abrufs manuell geänderte Position wird als Konflikt gemeldet und nicht überschrieben. Auch ohne Prüfdialog bleiben die exakte Artikelzuordnung und die festen Datentypen/Einheiten erhalten; inkompatible Werte werden mit einem Hinweis ausgelassen.

Je Position **Daten vervollständigen** wählen. Der Browser-Scraper sucht die Reichelt-Artikelnummer und akzeptiert nur einen exakt passenden Treffer. Dafür wird kein API-Schlüssel benötigt. Die Vorschau zeigt Quelle, Abrufzeit, bisherige Angaben und Vorschläge. Neue/leere Angaben und eine noch nicht zugeordnete Kategorie sind vorausgewählt; abweichende bereits gepflegte Werte werden erst nach ausdrücklicher Auswahl ersetzt. Mit **Ausgewählte Änderungen speichern** übernehmen oder mit **Abbrechen** alles unverändert lassen.

Bei Widerständen werden beispielsweise Kategorie, Widerstandswert in Ω, Toleranz in %, Widerstandsart (z. B. Metallschicht), Bauform, Leistung in W, Typ, Hersteller, MPN sowie Produkt- und Datenblattlink ergänzt. Weitere erkannte Angaben sind Ausführung, Spezifikation, Temperaturkoeffizient als Text sowie bei anderen Bauteilen Kapazität in µF, Spannungsfestigkeit in V, Material und Rastermaß in mm. Unbekannte Angaben bleiben leer; Bereiche oder widersprüchliche Werte werden als Hinweis angezeigt. Merkmale werden nur in der zur Kategorie passenden Einheit gespeichert. Fehlende Merkmalsdefinitionen werden beim bestätigten Speichern ergänzt; vorhandene Typen oder Einheiten werden nicht verändert.

Die Ergänzungen werden am verknüpften Bauteil gespeichert und sind damit auch in anderen Projekten sichtbar. Bedarfs-, Wareneingangs- und Bestandsmengen werden nicht verändert. Die ausgewählten Angaben müssen innerhalb von 30 Minuten übernommen werden; bei zwischenzeitlichen Änderungen an Bauteilen/Stammdaten ist eine neue Vorschau nötig.

Voraussetzungen auf dem **Backend-Rechner**: Node.js, die mit `npm --prefix frontend ci` installierten Playwright-Pakete und Chromium/Chrome. Lokal wird `chromium` bzw. `google-chrome` im PATH automatisch erkannt. Ein abweichender Browserpfad lässt sich über `REICHELT_BROWSER_PATH=/pfad/zum/chromium` konfigurieren; `REICHELT_SCRAPER_ENABLED=0` deaktiviert den direkten Abruf. Für den VPS müssen Node.js im Dienst-PATH sowie die Browserbibliotheken verfügbar sein und `frontend/node_modules` erhalten bleiben. Der Kernablauf für Bedarf und Wareneingang benötigt den Scraper nicht.

Produktdaten werden 24 Stunden zwischengespeichert. Pro Datenbank läuft höchstens ein externer Abruf gleichzeitig, mit mindestens drei Sekunden zwischen Abrufstarts und einer zusätzlichen Pause zwischen Suche und Produktseite. Bei HTTP 403/429/503 wird der Abruf ohne Änderungen abgebrochen und für 60 Sekunden pausiert. Der Scraper löst keine CAPTCHAs und meldet geänderte oder nicht erreichbare Produktseiten als Fehler. Die Einrichtung ist in Migration `0003` enthalten. Ein Live-Abruf für `METALL 330` einschließlich Übernahme wurde am 29.10.2026 erfolgreich geprüft; die Erreichbarkeit bleibt vom Shop abhängig.

Das vom Nutzer genannte [jkreucher/ReicheltAPI](https://github.com/jkreucher/ReicheltAPI) wurde als Referenz geprüft. Es dokumentiert einen Python-Scraper mit BeautifulSoup und steht unter GPL-3.0. Unsere Browserauswertung wurde anhand der aktuellen Produktseite separat implementiert; das Repository wird nicht als zusätzliche Abhängigkeit eingebunden. Der reguläre Chromium-Abruf wurde gewählt, weil direkte HTTP-Anfragen in der Arbeitsumgebung eine Schutzseite liefern.

### Optionale Produktdaten

Ohne externe Konfiguration funktioniert der vollständige Listen- und Wareneingangsablauf. Für Produktvorschläge über den unabhängigen Anbieter everydata.io `REICHELT_API_KEY` ausschließlich in der Backend-Umgebung setzen und das Backend neu starten. Beispiel für lokale Starts: `REICHELT_API_KEY=… COOKIE_SECURE=0 .venv/bin/flask --app backend.app run --host 127.0.0.1`. Den Schlüssel nicht in Frontendcode oder das Repository schreiben. Die VPS-Umgebungsvorlage enthält einen optionalen Eintrag.

In der Importvorschau lässt sich **Produktdaten ergänzen** je neuer Position ausdrücklich auslösen. Pro Versuch erfolgen üblicherweise eine Suche und ein Detailabruf. Ein API-Konto/Schlüssel und dessen Kontingent werden benötigt; es findet kein automatischer Abruf beim Upload statt. Nur ein eindeutiger Treffer mit exakt passender Artikelnummer wird übernommen. Vorschläge für Titel, Hersteller, MPN, Bauform, Produktlink und Kategorie vor dem Import prüfen. Eindeutige Zahlenwerte werden nur in passende feste Kategorieeinheiten übernommen (z. B. 100 nF → 0,1 µF). Bei unbekannten Daten oder einem API-Fehler bleibt der Import ohne diese Ergänzung möglich. Datenblattlinks werden von diesem Provideradapter derzeit nicht automatisch ergänzt.

Die Recherche, Quellen und die Abgrenzung zu den offiziellen Reichelt-Zugängen OCI/BMEcat stehen in [REICHELT_IMPORT.md](REICHELT_IMPORT.md). Der echte API-Abruf wurde mangels Nutzerschlüssel nicht verifiziert; automatisierte Tests prüfen den Adapter mit lokalen Antworten.

## API

Alle Endpunkte unter `/api`. Antworten sind JSON, außer dem ZIP-Export. Anmeldung per Cookie `parts_session`; schreibende Aufrufe benötigen `X-CSRF-Token`. Kein CORS-Zugriff vorgesehen.

| Methode / Pfad | Zweck |
| --- | --- |
| `POST /login` | `{username,password}` → `{csrf,username}` |
| `GET /session`, `POST /logout` | Sitzung abrufen / beenden |
| `PUT /account` | `{username,current_password,new_password?}` → Zugangsdaten ändern und alle Sitzungen beenden |
| `POST /settings/reset/preview` | Anzahl betroffener und erhaltener Datensätze, sitzungsgebundenes `token` |
| `POST /settings/reset` | `{token,current_password,confirmation:"ZURÜCKSETZEN"}` → automatisch sichern, Inventar löschen, Kategorien/Konto erhalten, Sitzungen beenden |
| `GET, POST /parts` | Liste mit Suche / Bauteil anlegen |
| `GET, PUT, DELETE /parts/<id>` | Details / ändern / löschen (`?confirm=yes`) |
| `GET, POST /categories`, `/locations`, `/suppliers` | Stammdaten auflisten / anlegen |
| `GET, PUT, DELETE /<stammdaten>/<id>` | Stammdaten verwalten |
| `POST /parts/<id>/offers` | Lieferantenangebot anlegen |
| `GET, PUT, DELETE /offers/<id>` | Angebot verwalten |
| `POST /parts/<id>/stock` | `{action,location_id,quantity,target_id?}` |
| `GET /demands` | Projektbedarfslisten mit Mengenübersicht |
| `GET, PUT, DELETE /demands/<id>` | Liste / Projektname ändern / Liste löschen (`?confirm=yes`) |
| `POST /demands/import` | Multipart `file`, optional `project_name` → Vorschau; JSON `{token,name,items:[{index,name,category_id}]}` → übernehmen |
| `POST /demands/import/enrich` | `{token,index}` → optionale Produktvorschläge für eine neue Position |
| `GET /demands/import-options` | Verfügbarkeit der optionalen Produktabfrage, ohne Schlüssel |
| `POST /demands/<id>/enrich` | `{item_id}` → Produktvorschläge für eine bestehende Projektposition |
| `POST /demands/<id>/enrich/apply` | `{token,selected:[Änderungsschlüssel]}` → ausgewählte Vorschläge übernehmen |
| `POST /demands/<id>/enrich/auto` | `{item_id}` → Position ohne Vorschau automatisch ergänzen; liefert `part`, `category`, `changed`, `warnings`, `cached`. Bei Abruffehlern gegebenenfalls `blocked` und `retry_after`; die Oberfläche verarbeitet die Positionen seriell. |
| `POST /parts/reichelt/preview` | `{identifier}` → Produktvorschau anhand exakter Reichelt-Artikelnummer oder Herstellerteilenummer |
| `POST /parts/reichelt/create` | `{token,part:{name,manufacturer,mpn,package,description,notes,attributes},manual_complete:false}` → geprüftes neues Bauteil mit Reichelt-Angebot anlegen; Kategorie und Quelle aus der serverseitigen Vorschau |
| `POST /demands/<id>/receive` | `{request_id,version,items:[{item_id,quantity,location_id}]}` → atomarer Wareneingang |
| `GET /export` | CSV-ZIP herunterladen |
| `POST /import` | Multipart `file` (einzelne CSV, anhand der Kopfzeile erkannt; alternativ vollständiges Export-ZIP); Vorschau, dann `apply=yes` und `digest` übernehmen |

Bestandsaktionen: `add`, `remove`, `set`, `transfer`. `quantity` ist positiv, bei `set` auch null erlaubt; `target_id` wird nur bei `transfer` benötigt. Listenparameter: `q`, `category_id`, `location_id`, `in_stock=1`, `field`, `min`, `max`, `value`, `sort` (`name`, `manufacturer`, `mpn`), `direction=desc`, `page`. Merkmalsfilter benötigen eine Kategorie. Erfolgreiche Anlage: 201, Validierungsfehler: 400, fehlende Sitzung: 401, CSRF: 403, nicht gefunden: 404, Referenz-/Eindeutigkeitskonflikt: 409, Anmeldebegrenzung: 429, Datenbank vorübergehend nicht verfügbar: 503.

## Linux-VPS mit Apache

Die Dateien unter `deploy/` sind anpassbare Vorlagen. Zuerst Domain auf den VPS richten und ein gültiges HTTPS-Zertifikat einrichten. Vorhandene Apache-VHosts vorher sichern. Die Beispiele nehmen `/opt/partsdb` als Codeverzeichnis und `/var/lib/partsdb` als privaten Datenbereich an.

1. Dienstbenutzer `partsdb` ohne interaktive Anmeldung anlegen. Projekt unter `/opt/partsdb` installieren. `/var/lib/partsdb` und `/opt/partsdb/instance` anlegen, dem Dienstbenutzer zuweisen und mit Modus 700 schützen. Apache benötigt ausschließlich Leserechte auf `frontend/dist` und Zugriff auf seine übergeordneten Verzeichnisse.
2. Python-Umgebung und Pakete wie oben installieren; `npm --prefix frontend ci` und `npm --prefix frontend run build` ausführen. Der Kerndienst benötigt kein Node.js; für den optionalen Browser-Scraper müssen Node.js, Playwright-Pakete und Chromium auch zur Laufzeit verfügbar bleiben (siehe Reichelt-Abschnitt).
3. `deploy/partsdb.env.example` nach `/etc/partsdb.env` kopieren; Eigentümer root, Gruppe partsdb, Modus 640. Datenbankpfad bei Bedarf anpassen. `COOKIE_SECURE=1` und `TRUST_PROXY=1` für die Vorlage verwenden.
4. Migration und Konto als Dienstbenutzer ausführen, mit identischem `DATABASE_URL` wie im Dienst. Beispielsweise aus `/opt/partsdb`:

```bash
sudo -u partsdb env DATABASE_URL=sqlite:////var/lib/partsdb/parts.sqlite \
  .venv/bin/flask --app backend.app migrate
sudo -u partsdb env DATABASE_URL=sqlite:////var/lib/partsdb/parts.sqlite \
  .venv/bin/flask --app backend.app set-user
```

5. Die drei systemd-Dateien aus `deploy/` nach `/etc/systemd/system/` übernehmen. Die vorhandene Umgebung und Installationspfade prüfen; dann:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now partsdb.service partsdb-backup.timer
```

6. `deploy/apache.conf` als eigenen VHost einrichten: Domain und Zertifikatspfade ersetzen. Module `ssl`, `proxy`, `proxy_http`, `headers` aktivieren (auf Debian/Ubuntu mit `a2enmod`). `apachectl configtest` ausführen und Apache erst bei erfolgreichem Ergebnis neu laden. Auf manchen Distributionen heißt der Dienst `httpd`.
7. Login, Suche, Bestandsänderung und Export über die öffentliche HTTPS-Adresse prüfen. `journalctl -u partsdb` und `systemctl list-timers partsdb-backup.timer` kontrollieren. Firewall: nur die vorgesehenen öffentlichen Dienste öffnen; Gunicorn bleibt auf Loopback.

Apache überschreibt `X-Forwarded-Proto`; Gunicorn darf bei `TRUST_PROXY=1` nicht öffentlich erreichbar sein. Zur Anmeldebegrenzung wird ohne Vertrauen in Forwarded-IP-Header die Proxy-Adresse verwendet. Für dieses einzelne Konto bedeutet das eine gemeinsame Sperre nach fünf Fehlversuchen in 15 Minuten.

## Sicherung und Wiederherstellung

Manuell (mit dem produktiven Datenbankpfad in der Umgebung):

```bash
.venv/bin/flask --app backend.app backup /var/lib/partsdb/backups
```

Der Befehl verwendet die SQLite-Backup-API und funktioniert bei laufendem Dienst. Er bereinigt eigene Backups nach 14 Tagen. Backups enthalten auch Konto und Sitzungen und werden mit Modus 600 angelegt. Zusätzlich eine Kopie außerhalb des VPS aufbewahren.

Wiederherstellung:

1. `partsdb.service` und Backup-Timer stoppen; aktuelle Datenbank zur Rückfallmöglichkeit sichern.
2. Backup mit `sqlite3 DATEI 'PRAGMA integrity_check;'` prüfen (Ergebnis `ok`).
3. Sicherung an den konfigurierten Datenbankpfad kopieren, Eigentümer `partsdb:partsdb`, Modus 600 setzen. Eventuelle alte `-wal`-/`-shm`-Dateien der gestoppten Datenbank entfernen.
4. `migrate` mit derselben Dienstumgebung ausführen; anschließend `set-user`, um alte Sitzungen zu widerrufen.
5. Dienst und Timer starten; Anmeldung und einen bekannten Bestand prüfen.

Updates: Backup erstellen, Dienst stoppen, Code und Abhängigkeiten aktualisieren, Vite bauen, Migrationen ausführen, Dienst starten und Kernabläufe prüfen. Bei einer fehlgeschlagenen Migration passenden Code und Datenbanksicherung gemeinsam wiederherstellen.

## Verifikationsstand dieser Arbeitsumgebung

Die benötigten Abhängigkeiten sind installiert und `pip check` meldet keine Konflikte.

- **66 Flask-Integrationstests bestanden:** Anmeldung, CSRF, Anmeldebegrenzung, konkurrierende Entnahmen, atomare Bestandsaktionen, Referenzschutz und Hierarchiezyklen, Suche und technische Merkmale, sichere Lieferantenlinks, CSV-Rundlauf und Rollback, Bindung des Imports an eine aktuelle Vorschau, HTTPS-Proxy und Cookie-Flags, Passwortwechsel mit Sitzungswiderruf sowie Migration und Backup-Integrität. Der direkte Einzel-CSV-Import wird für alle sechs Tabellen mit UTF-8-BOM, Vorschau/Übernahme, Dateibindung, Zustandsänderungen und Fehler-Rollback geprüft. Zusätzliche Tests decken Trennzeichenerkennung, Excel-`sep=`-Zeilen, mehrzeilige Textfelder und verständliche Quotingfehler mit Zeilennummer ab. Zwölf Tests prüfen Reichelt-Import, vorhandene Artikel, Teillieferungen, atomaren Rollback, Wiederholungsschutz, konkurrierende Wareneingänge, Zahlenüberlauf, Vorschauablauf, optionale Datenanreicherung sowie Migration und Backup der Projektlisten. Sechs Tests prüfen die nachträgliche Ergänzung, selektives Speichern, Schutz vorhandener Einheiten und Werte, Cache/Abruflimits, gesperrte Abrufe und widersprüchliche Spezifikationen. Zwei weitere Tests prüfen Herkunft, manuellen Pflegestand und die Bestätigung unveränderter älterer Produktdaten. Acht weitere Tests prüfen Reichelt-Neuanlage über Artikelnummer und Herstellerteilenummer, Cache-Zuordnung, Duplikate, Vorschauablauf, Kategorieänderungen, feste Einheiten, manuelle Prüfzustände, Fehler-Rollback und konkurrierende Anlage. Fünf weitere Tests prüfen den vollständigen Reichelt-Kategorienbaum, Elternbeziehungen, identische Bezeichnungen, Migration vorhandener Daten sowie Filter über Unterkategorien ohne Einheitenvermischung. Acht Tests prüfen die direkte automatische Ergänzung ohne Vorschau, bereits erhaltene Positionen, eigene Angaben, Einheitenkonflikte, Abruffehler/Sperren, parallele Änderungen und Sitzungs-/CSRF-Schutz. Zehn weitere Tests prüfen Kontoänderungen, Hash-Speicherung, Sitzungswiderruf einschließlich wartender Schreibanfragen, Reset mit vollständiger Sicherung und Kategorieerhalt, Schutz vor veralteten Vorschauen und aktiven Abrufen, Rollback bei fehlgeschlagener Sicherung, CLI-Varianten und Vorrang der Umgebung vor `.env`. Der zusätzliche Browserablauf prüft den gesamten Sammellauf einschließlich Stoppen, Abrufpause, Fehlerfortsetzung, Wareneingangsentwurf und gespeicherten Daten nach Neuladen. Der Browserablauf prüft extrem lange Texte bei 320, 390, 768 und 1280 Pixeln sowie die gespeicherten Kennzeichen.
- **Vite-Produktionsbuild bestanden** mit Vite 7.3.7; HTML, CSS und JavaScript unter `frontend/dist` erzeugt.
- **Gunicorn-Konfigurationsprüfung bestanden** (`gunicorn --check-config 'backend.app:create_app()'`).
- Python-Kompilierung und JavaScript-Syntaxprüfung bestanden. Das SQLite-Schema wurde zusätzlich direkt auf Mengenbegrenzung, Eindeutigkeit, Referenzschutz, Kaskade und Backup geprüft.
- **Playwright-MCP-Browserabnahme bestanden (29.10.2026):** zwölf vollständige Szenarien mit separater Testdatenbank, Desktop- und Mobilansicht sowie abschließender SQLite-Integritäts- und Referenzprüfung. Keine unerwarteten JavaScript-, Netzwerk- oder Serverfehler. Behoben wurden leere GET-Anfragen mit JSON-Header (Anmeldung/Stammdaten blockiert), ungültige Seitennavigation nach Löschung, die ausgeblendete mobile Abmeldung und stehenbleibende Importfehlermeldungen. Das fehlende Favicon wurde ergänzt.

**Noch offen:** tatsächlicher HTTP-/Apache-/HTTPS-Betrieb auf dem Zielserver. Die lokale Browserabnahme läuft über Vite → Flask → SQLite; die VPS-Konfiguration liegt weiterhin als Vorlage vor und wurde auf keinem Server aktiviert. Vor Produktivbetrieb Apache-Proxy, HTTPS-Cookies, systemd-Dienst und Backup-Timer auf dem Zielsystem prüfen.
