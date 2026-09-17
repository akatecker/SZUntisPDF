# SZUntisPDF – Stundenplan als PDF

Zeigt den WebUntis-Stundenplan eines Kindes an und druckt ihn als
Wochenübersicht – oder sichert ihn als PDF.

---

## Starten

**macOS** – beim ersten Mal:

1. Rechtsklick (oder Ctrl+Klick) auf `SZUntisPDF` → **Öffnen**
2. Im Hinweisfenster noch einmal auf **Öffnen** klicken

Der Umweg ist einmalig nötig, weil das Programm nicht bei Apple registriert
ist. Ab dann genügt ein Doppelklick. Falls macOS meldet, die Datei sei
„beschädigt", hilft im Programm *Terminal* dieser Befehl – danach normal öffnen:

```
xattr -dr com.apple.quarantine ~/Downloads/SZUntisPDF
```

**Windows** – Doppelklick auf `SZUntisPDF.exe`. Meldet sich der SmartScreen-Filter
mit „Der Computer wurde geschützt", auf **Weitere Informationen** und dann
**Trotzdem ausführen** klicken. Auch das ist einmalig.

Es öffnet sich ein kleines schwarzes Fenster und kurz darauf der Browser mit
dem Stundenplan. **Das schwarze Fenster muss offen bleiben**, solange man das
Programm benutzt; Schließen beendet es.

---

## Einrichten

Beim ersten Start fragt das Programm nach dem Zugang. Den QR-Code dafür gibt es
in WebUntis unter **Profil → Freigaben → Zugriff über Untis Mobile**.

Drei Wege stehen zur Wahl:

| Weg | Wann |
|---|---|
| **Kamera** | QR-Code am Bildschirm oder auf Papier vor die Kamera halten |
| **Bild** | Screenshot oder Foto des Codes auswählen oder hineinziehen |
| **Manuell** | Die vier Werte abtippen – sie stehen unter dem QR-Code |

Danach ist der Zugang gespeichert; beim nächsten Start geht es direkt zum
Stundenplan. Über **Konto** oben rechts lässt er sich wieder entfernen.

---

## Drucken und als PDF sichern

Der Knopf **Drucken / PDF** öffnet den Druckdialog des Browsers.

- **macOS:** unten links auf *PDF* → *Als PDF sichern*
- **Windows:** als Drucker *Microsoft Print to PDF* wählen

Gedruckt wird eine Wochenübersicht auf A4 quer. Entfallene Stunden stehen
durchgestrichen und rot.

---

## Was die Ansicht zeigt

Oben lässt sich einstellen, wie stark der **Klassenplan** einbezogen wird.
Hintergrund: Lehrkräfte tragen Änderungen dort oft früher ein als im
persönlichen Plan.

| Einstellung | Bedeutung |
|---|---|
| Nur mein Plan | ausschließlich der persönliche Stundenplan |
| Mein Plan + Klassenänderungen | zusätzlich Änderungen der Klasse, die eigene Fächer betreffen *(Voreinstellung)* |
| Klassenplan vollständig | alles, auch Gruppen, die das Kind nicht besucht |

Einträge, die **nur** aus dem Klassenplan stammen, sind gestrichelt umrandet.
Sie können eine noch nicht übertragene Änderung sein – oder eine Parallelgruppe,
die das eigene Kind nicht betrifft.

Ein `*` hinter einem Fach heißt: Die Abkürzung steht nicht wörtlich in der
Fächerliste der Schule, die Bezeichnung wurde aus der Stammform abgeleitet.

---

## Datenschutz

Das Programm läuft vollständig auf dem eigenen Rechner und spricht nur mit
WebUntis. Es gibt keinen Server dazwischen, nichts wird an Dritte übertragen.

Der gespeicherte Zugang liegt hier:

- **macOS:** `~/Library/Application Support/SZUntisPDF/konto.json`
- **Windows:** `%APPDATA%\SZUntisPDF\konto.json`

Dieser Zugangsschlüssel ist **so schützenswert wie ein Passwort** – er erlaubt
dauerhaft Lesezugriff auf das WebUntis-Konto. Das Programm selbst enthält keine
Zugangsdaten und kann bedenkenlos weitergegeben werden.

Soll der Zugang weg: **Konto** im Programm, oder die Datei oben löschen.
Wurde der QR-Code versehentlich weitergegeben, lässt sich in WebUntis unter
*Profil → Freigaben* ein neuer Schlüssel erzeugen; der alte wird damit ungültig.
