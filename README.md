# SZUntisPDF

Zeigt den WebUntis-Stundenplan eines Kindes an und druckt ihn als
Wochenübersicht auf A4 quer – oder sichert ihn als PDF. Für **macOS, Windows
und Android**. Kein Installer, keine Laufzeitumgebung.

Fächer erscheinen im Klartext statt als Kürzel – das leistet Untis Mobile nicht.

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
android/                Android-App (Kotlin), teilt sich die Oberflaeche
  app/src/main/java/.../Untis.kt          WebUntis-Client, TOTP, Zusammenfuehrung
  app/src/main/java/.../LokalerServer.kt  bedient die WebView
  app/src/main/java/.../MainActivity.kt   WebView, Kamera, Drucken
  app/src/main/java/.../Faecher.kt        erzeugt aus szuntis/subjects.py
werkzeuge/
  icons_bauen.py        Programmsymbole aus dem Schullogo
  faecher_nach_kotlin.py  erzeugt die Kotlin-Fassung der Faecherliste
  rauchtest.py          prueft ein gebautes Programm ohne Zugangsdaten
```

## Android

Dieselbe Oberfläche, dieselbe Zusammenführungslogik – in Kotlin statt Python.
Die HTML-Dateien liegen unverändert in den App-Assets; ein kleiner Server auf
`127.0.0.1` bedient die WebView, weil eine WebView ihrerseits CORS durchsetzt
und WebUntis deshalb auch dort nicht direkt ansprechen kann.

Das Drucken übernimmt Androids eigenes Druck-Rahmenwerk über
`WebView.createPrintDocumentAdapter()`; „Als PDF speichern" ist dort ein
normales Druckziel. Die APK wiegt **0,8 MB**.

Ein Intent-Filter auf `untis://setschool` bedeutet: Wer den QR-Code mit
irgendeiner Kamera-App scannt, landet direkt in dieser App.

Die Fächerliste wird aus derselben Quelle erzeugt wie die Desktop-Fassung:

```bash
python3 werkzeuge/faecher_nach_kotlin.py
cd android && ./gradlew :app:assembleRelease
```

Gebaut wird gegen JDK 17; `JAVA_HOME` und `ANDROID_HOME` müssen gesetzt sein.

### Signatur

Liegt `android/schluessel.jks` vor, wird damit signiert – sonst mit dem
Debug-Schlüssel. In GitHub Actions kommt der Schlüssel aus den Secrets
`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORT` und
`ANDROID_SCHLUESSEL_ALIAS`. Ohne sie lässt sich die APK zwar installieren, aber
nicht über eine ältere Fassung drübersetzen, weil jede Veröffentlichung eine
andere Signatur bekäme.

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
