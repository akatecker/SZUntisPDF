# SZUntisPDF – Stundenplan als PDF

Zeigt den WebUntis-Stundenplan eines Kindes an und druckt ihn als
Wochenübersicht – oder sichert ihn als PDF.

---

## Starten

**macOS** – `SZUntisPDF.app` am besten in den Ordner *Programme* ziehen. Beim
ersten Start:

1. Rechtsklick (oder Ctrl+Klick) auf die App → **Öffnen**
2. Im Hinweisfenster noch einmal auf **Öffnen** klicken

Der Umweg ist einmalig nötig, weil das Programm nicht bei Apple registriert
ist. Ab dann genügt ein Doppelklick. Falls macOS meldet, die App sei
„beschädigt", hilft im Programm *Terminal* dieser Befehl – danach normal öffnen:

```
xattr -dr com.apple.quarantine /Applications/SZUntisPDF.app
```

**Windows** – Doppelklick auf `SZUntisPDF.exe`. Meldet sich der SmartScreen-Filter
mit „Der Computer wurde geschützt", auf **Weitere Informationen** und dann
**Trotzdem ausführen** klicken. Auch das ist einmalig.

Es öffnet sich ein Fenster mit dem Stundenplan – ohne Adresszeile, wie ein
gewöhnliches Programm. **Das Fenster zu schließen beendet SZUntisPDF**, ganz
so, wie man es erwartet. Alternativ gibt es oben rechts einen Knopf *Beenden*.

Sollte sich kein Fenster zeigen, steht die Adresse zum Kopieren in einer Datei:

- **macOS:** `~/Library/Application Support/SZUntisPDF/adresse.txt`
- **Windows:** `%APPDATA%\SZUntisPDF\adresse.txt`

**Android** – die Datei `SZUntisPDF-android.apk` antippen. Android fragt einmalig,
ob Apps aus dieser Quelle installiert werden dürfen: **Einstellungen** →
**Installieren** erlauben → zurück und noch einmal antippen. Danach liegt die App
wie jede andere im App-Raster.

Ein Hinweis von Google Play Protect („unbekannter Entwickler") kann erscheinen –
**Trotzdem installieren** wählen. Die App stammt nicht aus dem Play Store.

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

Auf Android geht es auch ohne die App zu öffnen: Wird der QR-Code mit einer
beliebigen Kamera-App gescannt, bietet Android SZUntisPDF zum Öffnen an und der
Zugang ist sofort eingerichtet.

Danach ist der Zugang gespeichert; beim nächsten Start geht es direkt zum
Stundenplan. Über **Konto** oben rechts lässt er sich wieder entfernen.

---

## Stundenplan oder Hausaufgaben

Oben lässt sich zwischen zwei Ansichten umschalten:

**Stundenplan** – das Wochenraster, quer auf A4.

**Hausaufgaben** – alles, was in dieser Woche zu tun ist, nach Fälligkeit
sortiert und hochkant auf A4. Zu jeder Aufgabe stehen Fach, Lehrkraft, der
Tag der Aufgabe und das Datum, an dem sie fällig ist.

Die Liste zeigt bewusst auch Aufgaben, die erst **nach** der angezeigten Woche
fällig sind – sie wurden ja in dieser Woche aufgegeben und sind jetzt zu
erledigen. Solche Einträge sind mit *nach dieser Woche* gekennzeichnet, ebenso
*überfällige* und *heute* fällige.

Anhänge, die eine Lehrkraft an eine Aufgabe gehängt hat, werden erwähnt, lassen
sich aber nur in WebUntis selbst öffnen.

## Drucken und als PDF sichern

Der Knopf **Drucken / PDF** öffnet den Druckdialog – gedruckt wird, was gerade
angezeigt wird, im jeweils passenden Format.

- **macOS:** unten links auf *PDF* → *Als PDF sichern*
- **Windows:** als Drucker *Microsoft Print to PDF* wählen
- **Android:** oben als Ziel *Als PDF speichern* wählen

Der Stundenplan kommt quer auf A4, die Hausaufgabenliste hochkant. Entfallene
Stunden stehen durchgestrichen und rot.

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
- **Android:** im privaten Bereich der App; er verschwindet beim Deinstallieren

Dieser Zugangsschlüssel ist **so schützenswert wie ein Passwort** – er erlaubt
dauerhaft Lesezugriff auf das WebUntis-Konto. Das Programm selbst enthält keine
Zugangsdaten und kann bedenkenlos weitergegeben werden.

Soll der Zugang weg: **Konto** im Programm, oder die Datei oben löschen.
Wurde der QR-Code versehentlich weitergegeben, lässt sich in WebUntis unter
*Profil → Freigaben* ein neuer Schlüssel erzeugen; der alte wird damit ungültig.
