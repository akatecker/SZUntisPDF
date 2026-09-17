# SZUntisPDF

Zeigt den WebUntis-Stundenplan eines Kindes an und druckt ihn als
Wochenübersicht auf A4 quer – oder sichert ihn als PDF. Eine Datei, kein
Installer, keine Laufzeitumgebung.

Für Eltern: **[ANLEITUNG.md](ANLEITUNG.md)** – Start, Einrichtung, Drucken.
Fertige Programme liegen unter [Releases](../../releases).

---

## Aufbau

Die Oberfläche läuft im Browser, das Programm selbst ist ein kleiner lokaler
Server. Das ist kein Umweg, sondern folgt aus zwei Messungen:

**WebUntis erlaubt keine Cross-Origin-Zugriffe.** Der Preflight auf
`jsonrpc_intern.do` antwortet mit `405`, die Antwort trägt keinen
`Access-Control-Allow-Origin`-Header. Eine reine Webseite kann den Dienst also
nicht ansprechen – ein lokaler Prozess ist unvermeidbar.

**Er muss aber nicht die Oberfläche zeichnen.** Ein mitgeliefertes
GUI-Werkzeug kostet Platz, das die Aufgabe nicht braucht:

| Variante | Größe |
|---|---|
| PySide6, aggressiv entschlackt | 48,4 MB |
| Standardbibliothek + Browser | **7,1 MB** |

Der Browser bringt außerdem mit, was sonst eigener Code wäre: Kamera für den
QR-Scan, Druckdialog und PDF-Ausgabe. Übrig bleibt Python ohne ein einziges
Fremdpaket – TOTP aus `hmac`, HTTPS aus `urllib`, Server aus `http.server`.

```
start.py                Einstiegspunkt fuer das gepackte Programm
szuntis/
  __main__.py           Server starten, Browser oeffnen
  server.py             HTTP-Server und JSON-Schnittstelle
  untis.py              WebUntis-Client, TOTP, Zusammenfuehrung beider Plaene
  konto.py              Zugang im Benutzerprofil ablegen
  subjects.py           111 Faecherabkuerzungen (erzeugt)
  web/                  Oberflaeche: HTML, CSS, JavaScript, jsQR
werkzeuge/
  icons_bauen.py        Programmsymbole aus dem Schullogo
  rauchtest.py          prueft ein gebautes Programm ohne Zugangsdaten
```

## Anmeldung

Dieselbe JSON-RPC-Schnittstelle, die auch die Untis-Mobile-App nutzt: Aus dem
Base32-Schlüssel des QR-Codes wird pro Aufruf ein TOTP-Einmalcode berechnet.

Diese Schnittstelle ist von Untis **nicht dokumentiert und nicht zugesichert**;
sie kann sich ohne Ankündigung ändern. Offizielle Alternativen wären das
iCal-Abo (nur Termine) oder die
[Untis-Platform-API](https://developer.untis.com/) – letztere allerdings nur
für Integrationspartner mit Freischaltung durch die Schule.

## Persönlicher Plan und Klassenplan

Lehrkräfte tragen Änderungen oft zuerst im Klassenplan ein. Der ist allerdings
eine *Obermenge* und enthält auch Parallelgruppen, die das Kind nicht besucht.
Über neun Wochen gemessen: 241 eigene Stunden, davon **keine einzige**, die
nicht auch im Klassenplan stünde – umgekehrt rund 17 fremde Einträge pro Woche.

Darum hat der persönliche Plan immer Vorrang. Ein Klasseneintrag entfällt, wenn
er dieselbe Stunde meint – gleiche `lessonId` oder dasselbe Fach zur selben
Zeit. Meldet der Klassenplan für eine eigene Stunde einen anderen Status, gilt
die Angabe der Klasse. Was nur aus dem Klassenplan stammt, wird gestrichelt
dargestellt und ist damit als unsicher gekennzeichnet.

## Selbst bauen

```bash
python3 -m szuntis                      # direkt starten, ohne Paketierung
pip install pyinstaller
pyinstaller --noconfirm SZUntisPDF.spec
python3 werkzeuge/rauchtest.py dist/SZUntisPDF
```

Die Programme für macOS (Apple Silicon und Intel) und Windows entstehen in
GitHub Actions aus demselben Quellstand; siehe
[.github/workflows/release.yml](.github/workflows/release.yml). Ein Tag `v*`
legt zusätzlich ein Release an.

## Grenzen

Die Programme sind **nicht signiert**. macOS und Windows weisen sie beim ersten
Start ab; der Weg daran vorbei steht in der [ANLEITUNG](ANLEITUNG.md). Eine
echte Signatur bräuchte ein Apple-Entwicklerzertifikat bzw. ein
Windows-Code-Signing-Zertifikat.

Per E-Mail lassen sich die Dateien kaum verschicken – Gmail und Outlook
blockieren ausführbare Dateien auch in ZIP-Archiven. Ein Link auf das Release
oder einen Dateidienst ist der verlässlichere Weg.

Die Fächerliste in `szuntis/subjects.py` stammt aus dem Abkürzungsverzeichnis
des Schulzentrums Ungargasse und gilt für das Schuljahr 2026/27. Für andere
Schulen greift automatisch der Langname aus WebUntis.
