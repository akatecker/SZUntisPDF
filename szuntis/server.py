"""Lokaler Webserver - die Oberfläche läuft im Browser des Benutzers.

Warum nicht als Fensterprogramm: WebUntis erlaubt keine Cross-Origin-Zugriffe
(der Preflight antwortet mit 405), eine reine Webseite kann den Dienst also
nicht ansprechen. Ein kleiner lokaler Prozess muss dazwischen. Der muss aber
nicht auch noch die Oberfläche zeichnen - das kann der Browser besser, und er
bringt Kamera, Druckdialog und PDF-Ausgabe gleich mit. Das spart gegenüber
einem mitgelieferten GUI-Werkzeugkasten rund 40 MB.

Sicherheit: Der Server lauscht nur auf 127.0.0.1 und verlangt für alle
API-Aufrufe ein Einmal-Geheimnis, das beim Start erzeugt und dem Browser über
die Startadresse mitgegeben wird. Ohne das könnte jede beliebige Webseite im
selben Browser die Stundenplandaten abrufen.
"""

from __future__ import annotations

import datetime as dt
import http.server
import json
import mimetypes
import pathlib
import time
import secrets
import sys
import threading
import urllib.parse

from . import konto as kontoablage
from .untis import (Hausaufgabe, Modus, Termin, UntisFehler, UntisKonto, Zugang,
                    tls_kontext)


def web_ordner() -> pathlib.Path:
    """Ordner mit den Oberflächendateien - auch im gepackten Programm."""
    if getattr(sys, "frozen", False):  # von PyInstaller entpackt
        return pathlib.Path(sys._MEIPASS) / "web"  # type: ignore[attr-defined]
    return pathlib.Path(__file__).resolve().parent / "web"


def _termin_als_json(termin: Termin) -> dict:
    return {
        "beginn": termin.beginn.isoformat(timespec="minutes"),
        "ende": termin.ende.isoformat(timespec="minutes"),
        "tag": termin.beginn.date().isoformat(),
        "kuerzel": termin.kuerzel,
        "fach": termin.fach,
        "fachExakt": termin.fach_exakt,
        "lehrkraft": termin.lehrkraft,
        "raum": termin.raum,
        "klasse": termin.klasse,
        "status": termin.status,
        "info": termin.info,
        "entfaellt": termin.entfaellt,
        "ausKlassenplan": termin.aus_klassenplan,
        "klassenHinweis": termin.klassen_hinweis,
    }


def _hausaufgabe_als_json(aufgabe: Hausaufgabe) -> dict:
    return {
        "aufgegeben": aufgabe.aufgegeben.isoformat(),
        "faellig": aufgabe.faellig.isoformat(),
        "kuerzel": aufgabe.kuerzel,
        "fach": aufgabe.fach,
        "fachExakt": aufgabe.fach_exakt,
        "lehrkraft": aufgabe.lehrkraft,
        "text": aufgabe.text,
        "anmerkung": aufgabe.anmerkung,
        "erledigt": aufgabe.erledigt,
        "anhaenge": aufgabe.anhaenge,
        "laeuftLaenger": aufgabe.laeuft_laenger,
    }


class Zustand:
    """Gemeinsamer Zustand aller Anfragen - ein Konto, eine Sitzung."""

    def __init__(self) -> None:
        self.geheimnis = secrets.token_urlsafe(24)
        self._konto: UntisKonto | None = None
        self._name: str = ""
        self._sperre = threading.Lock()
        #: Zeitpunkt des letzten Lebenszeichens der Oberfläche. Bleibt es aus,
        #: ist das Fenster zu und das Programm kann sich beenden.
        self.letztes_lebenszeichen = time.monotonic()
        #: Wird gesetzt, wenn sich das Programm beenden soll.
        self.schluss = threading.Event()
        #: Wie lange ohne Lebenszeichen gewartet wird, in Sekunden.
        self.geduld = 600.0

    def konto(self) -> UntisKonto | None:
        return self._konto

    def anmelden(self, zugang: Zugang) -> str:
        """Meldet an und merkt sich die Sitzung. Wirft bei falschen Daten."""
        konto = UntisKonto(zugang)
        name = konto.anmelden()
        with self._sperre:
            self._konto = konto
            self._name = name
        return name

    def abmelden(self) -> None:
        with self._sperre:
            self._konto = None
            self._name = ""

    @property
    def name(self) -> str:
        return self._name

    def aus_ablage_laden(self) -> bool:
        """Versucht, ein gespeichertes Konto zu übernehmen."""
        zugang = kontoablage.laden()
        if zugang is None:
            return False
        try:
            self.anmelden(zugang)
        except UntisFehler:
            return False
        return True


class Anfrage(http.server.BaseHTTPRequestHandler):
    """Bedient die Oberfläche und eine kleine JSON-Schnittstelle."""

    server_version = "SZUntisPDF"
    sys_version = ""
    zustand: Zustand  # wird über functools.partial gesetzt

    # -- Hilfen ------------------------------------------------------------

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - Qt/BaseHTTP-Signatur
        pass  # keine Konsolenausgabe bei jedem Bild

    def _antworte(self, code: int, inhalt: bytes, typ: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(inhalt)))
        self.send_header("Cache-Control", "no-store")
        # Verhindert, dass eine fremde Seite die Antworten einbettet.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(inhalt)

    def _json(self, daten: dict, code: int = 200) -> None:
        self._antworte(code, json.dumps(daten, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

    def _fehler(self, meldung: str, code: int = 400) -> None:
        self._json({"fehler": meldung}, code)

    def _rumpf(self) -> dict:
        laenge = int(self.headers.get("Content-Length") or 0)
        if not laenge:
            return {}
        try:
            return json.loads(self.rfile.read(laenge).decode("utf-8"))
        except ValueError:
            return {}

    def _zugelassen(self) -> bool:
        """Nur der eigene Browser mit dem Startgeheimnis darf an die API."""
        gastgeber = (self.headers.get("Host") or "").split(":")[0]
        if gastgeber not in ("127.0.0.1", "localhost"):
            return False  # schützt vor DNS-Rebinding

        mitgeschickt = self.headers.get("X-SZU-Schluessel", "")
        if not mitgeschickt:
            # navigator.sendBeacon kann keine Kopfzeilen setzen; für den
            # Abschiedsgruß beim Fensterschließen ist die Abfrage der einzige
            # Weg. Unbedenklich: Es geht nur um die Loopback-Adresse, und ohne
            # das Geheimnis passiert weiterhin nichts.
            felder = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            mitgeschickt = felder.get("s", [""])[0]
        return secrets.compare_digest(mitgeschickt, self.zustand.geheimnis)

    # -- Weiterleitung -----------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler
        pfad = urllib.parse.urlparse(self.path).path
        if pfad.startswith("/api/"):
            if not self._zugelassen():
                return self._fehler("Nicht zugelassen.", 403)
            self.zustand.letztes_lebenszeichen = time.monotonic()
            return self._api_get(pfad)
        return self._datei_ausliefern(pfad)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler
        pfad = urllib.parse.urlparse(self.path).path
        if not pfad.startswith("/api/") or not self._zugelassen():
            return self._fehler("Nicht zugelassen.", 403)
        return self._api_post(pfad)

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler
        pfad = urllib.parse.urlparse(self.path).path
        if pfad != "/api/konto" or not self._zugelassen():
            return self._fehler("Nicht zugelassen.", 403)
        kontoablage.loeschen()
        self.zustand.abmelden()
        self._json({"ok": True})

    # -- Oberflächendateien ------------------------------------------------

    def _datei_ausliefern(self, pfad: str) -> None:
        name = "index.html" if pfad in ("/", "") else pfad.lstrip("/")
        ziel = (web_ordner() / name).resolve()
        if not ziel.is_file() or web_ordner().resolve() not in ziel.parents:
            return self._antworte(404, b"Nicht gefunden", "text/plain; charset=utf-8")
        typ, _ = mimetypes.guess_type(str(ziel))
        self._antworte(200, ziel.read_bytes(), typ or "application/octet-stream")

    # -- Schnittstelle -----------------------------------------------------

    def _api_get(self, pfad: str) -> None:
        if pfad == "/api/status":
            konto = self.zustand.konto()
            return self._json({
                "angemeldet": konto is not None,
                "name": self.zustand.name,
                "benutzer": konto.zugang.benutzer if konto else "",
                "schule": konto.zugang.schule if konto else "",
                "modi": [m.value for m in Modus],
                "standardModus": Modus.AENDERUNGEN.value,
                # Anzahl bekannter Wurzelzertifikate. Ist sie 0, scheitert jede
                # Verbindung zu WebUntis - der Rauchtest prüft genau das.
                "tlsZertifikate": tls_kontext().cert_store_stats().get("x509_ca", 0),
            })

        if pfad == "/api/puls":
            # Die Oberfläche meldet sich regelmäßig. Hört sie auf, wurde das
            # Fenster geschlossen - dann beendet sich das Programm von selbst.
            return self._json({"ok": True})

        if pfad == "/api/plan":
            konto = self.zustand.konto()
            if konto is None:
                return self._fehler("Kein Konto eingerichtet.", 409)
            felder = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                montag = dt.date.fromisoformat(felder.get("montag", [""])[0])
            except ValueError:
                return self._fehler("Ungültiges Datum.")
            modus = Modus.AENDERUNGEN
            gewuenscht = felder.get("modus", [""])[0]
            for kandidat in Modus:
                if kandidat.value == gewuenscht:
                    modus = kandidat
            try:
                termine = konto.termine(montag, montag + dt.timedelta(days=6), modus)
            except UntisFehler as fehler:
                return self._fehler(str(fehler), 502)
            return self._json({
                "name": self.zustand.name,
                "montag": montag.isoformat(),
                "modus": modus.value,
                "termine": [_termin_als_json(t) for t in termine],
            })

        if pfad == "/api/hausaufgaben":
            konto = self.zustand.konto()
            if konto is None:
                return self._fehler("Kein Konto eingerichtet.", 409)
            felder = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                montag = dt.date.fromisoformat(felder.get("montag", [""])[0])
            except ValueError:
                return self._fehler("Ungültiges Datum.")
            try:
                aufgaben = konto.hausaufgaben(montag)
            except UntisFehler as fehler:
                return self._fehler(str(fehler), 502)
            return self._json({
                "name": self.zustand.name,
                "montag": montag.isoformat(),
                "aufgaben": [_hausaufgabe_als_json(a) for a in aufgaben],
            })

        self._fehler("Unbekannter Aufruf.", 404)

    def _api_post(self, pfad: str) -> None:
        if pfad == "/api/beenden":
            self._json({"ok": True})
            self.zustand.schluss.set()
            return

        if pfad == "/api/schliesst":
            # Das Fenster geht zu - aber vielleicht nur, weil neu geladen wird.
            # Darum nicht sofort Schluss machen, sondern die Geduld des Wächters
            # auf wenige Sekunden verkürzen. Kommt gleich wieder eine Anfrage,
            # war es ein Neuladen und alles bleibt.
            # max(): Bei kurzer Geduld ergäbe die Differenz sonst einen Zeitpunkt
            # in der Zukunft, und der Wächter schlüge nie an.
            self.zustand.letztes_lebenszeichen = (
                time.monotonic() - max(self.zustand.geduld - 8.0, 0.0)
            )
            self._json({"ok": True})
            return

        if pfad != "/api/konto":
            return self._fehler("Unbekannter Aufruf.", 404)

        daten = self._rumpf()
        try:
            if daten.get("qr"):
                zugang = Zugang.aus_qr(daten["qr"])
            else:
                zugang = Zugang(
                    server=str(daten.get("server", "")).strip()
                    .removeprefix("https://").removeprefix("http://").rstrip("/"),
                    schule=str(daten.get("schule", "")).strip(),
                    benutzer=str(daten.get("benutzer", "")).strip(),
                    schluessel=str(daten.get("schluessel", "")).replace(" ", "").strip().upper(),
                )
        except ValueError as fehler:
            return self._fehler(str(fehler))

        if not all(kontoablage.dataclass_werte(zugang)):
            return self._fehler("Es fehlen noch Angaben.")

        try:
            name = self.zustand.anmelden(zugang)
        except UntisFehler as fehler:
            return self._fehler(str(fehler), 502)

        if daten.get("merken", True):
            kontoablage.speichern(zugang)
        self._json({"ok": True, "name": name, "benutzer": zugang.benutzer})


def starten(port: int = 0) -> tuple[http.server.ThreadingHTTPServer, Zustand]:
    """Startet den Server auf 127.0.0.1 und liefert ihn samt Zustand zurück."""
    zustand = Zustand()

    class Gebunden(Anfrage):
        pass

    Gebunden.zustand = zustand
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Gebunden)
    return server, zustand
