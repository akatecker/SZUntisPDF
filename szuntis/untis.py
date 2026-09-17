"""Schlanker WebUntis-Client für die Anmeldung per QR-Code-Schlüssel.

Nutzt dieselbe JSON-RPC-Schnittstelle wie die Untis-Mobile-App: Aus dem
Base32-Schlüssel des QR-Codes wird pro Aufruf ein TOTP-Einmalcode berechnet.

Kommt vollständig ohne Fremdpakete aus - TOTP, HTTPS und JSON kann die
Standardbibliothek. Das hält das fertige Programm bei rund 7 MB.
"""

from __future__ import annotations

import base64
import collections
import dataclasses
import datetime as dt
import enum
import hashlib
import hmac
import json
import struct
import time
import urllib.error
import urllib.request

from . import subjects

# Untis liefert Zeitstempel als "2026-09-15T08:15Z". Das Z ist irreführend:
# es sind Ortszeiten der Schule, keine UTC. Deshalb naiv parsen.
_ZEITFORMAT = "%Y-%m-%dT%H:%M"


class UntisFehler(RuntimeError):
    """Fehler der Gegenstelle oder der Anmeldung."""


@dataclasses.dataclass(frozen=True, slots=True)
class Zugang:
    """Die fünf Werte aus dem ``untis://setschool``-QR-Code."""

    server: str
    schule: str
    benutzer: str
    schluessel: str

    @classmethod
    def aus_qr(cls, qr: str) -> "Zugang":
        """Liest einen ``untis://setschool?...``-String ein."""
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(qr).query)
        fehlend = [k for k in ("url", "school", "user", "key") if k not in q]
        if fehlend:
            raise ValueError(f"QR-Code unvollständig, es fehlt: {', '.join(fehlend)}")
        return cls(q["url"][0], q["school"][0], q["user"][0], q["key"][0])


class Quelle(enum.StrEnum):
    """Woher ein Termin stammt."""

    EIGEN = "eigen"
    KLASSE = "klasse"


class Modus(enum.StrEnum):
    """Wie stark der Klassenplan einbezogen wird."""

    NUR_EIGEN = "Nur mein Plan"
    AENDERUNGEN = "Mein Plan + Klassenänderungen"
    KLASSE_VOLL = "Klassenplan vollständig"


@dataclasses.dataclass(slots=True)
class Termin:
    """Ein Eintrag im Stundenplan, bereits in Klartext aufgelöst."""

    beginn: dt.datetime
    ende: dt.datetime
    kuerzel: str
    fach: str
    fach_exakt: bool
    lehrkraft: str
    raum: str
    klasse: str
    status: str
    info: str
    entfaellt: bool
    quelle: Quelle = Quelle.EIGEN
    #: Gesetzt, wenn der Klassenplan für diese Stunde etwas anderes meldet
    #: als der persönliche Plan - dann gilt die Angabe der Klasse.
    klassen_hinweis: str = ""

    @property
    def zeitraum(self) -> str:
        return f"{self.beginn:%H:%M}–{self.ende:%H:%M}"

    @property
    def aus_klassenplan(self) -> bool:
        return self.quelle is Quelle.KLASSE


def _totp(schluessel: str, zeitpunkt: float | None = None) -> int:
    """RFC-6238-Einmalcode (SHA-1, 30 s, 6 Stellen) aus dem Base32-Schlüssel."""
    roh = schluessel.upper().replace(" ", "")
    key = base64.b32decode(roh + "=" * (-len(roh) % 8))
    zaehler = int((zeitpunkt if zeitpunkt is not None else time.time()) // 30)
    mac = hmac.new(key, struct.pack(">Q", zaehler), hashlib.sha1).digest()
    versatz = mac[-1] & 0x0F
    return (struct.unpack(">I", mac[versatz : versatz + 4])[0] & 0x7FFFFFFF) % 1_000_000


class UntisKonto:
    """Angemeldete Sitzung für genau ein WebUntis-Konto."""

    def __init__(self, zugang: Zugang, *, timeout: int = 25) -> None:
        self.zugang = zugang
        self.timeout = timeout
        self._stammdaten: dict | None = None
        self._benutzer: dict | None = None
        self._stammklasse: int | None = None

    # -- Transport ---------------------------------------------------------

    def _auth(self) -> dict:
        return {
            "clientTime": int(time.time() * 1000),
            "user": self.zugang.benutzer,
            "otp": _totp(self.zugang.schluessel),
        }

    def _rpc(self, methode: str, parameter: dict) -> dict:
        from urllib.parse import urlencode

        abfrage = urlencode({"m": methode, "school": self.zugang.schule, "v": "i2.2"})
        rumpf = json.dumps(
            {"id": "wux", "method": methode, "params": [parameter], "jsonrpc": "2.0"}
        ).encode("utf-8")
        anfrage = urllib.request.Request(
            f"https://{self.zugang.server}/WebUntis/jsonrpc_intern.do?{abfrage}",
            data=rumpf,
            headers={"Content-Type": "application/json", "User-Agent": "SZUntisPDF/1.0"},
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=self.timeout) as antwort:
                daten = json.loads(antwort.read().decode("utf-8"))
        except urllib.error.HTTPError as fehler:
            raise UntisFehler(
                f"{self.zugang.server} antwortete mit {fehler.code} {fehler.reason}"
            ) from fehler
        except urllib.error.URLError as fehler:
            raise UntisFehler(
                f"Keine Verbindung zu {self.zugang.server}: {fehler.reason}"
            ) from fehler
        except (TimeoutError, OSError) as fehler:
            raise UntisFehler(f"Keine Verbindung zu {self.zugang.server}: {fehler}") from fehler
        except ValueError as fehler:
            raise UntisFehler("Unerwartete Antwort (kein JSON) - Server erreichbar?") from fehler

        if "error" in daten:
            meldung = daten["error"].get("message", "unbekannt")
            code = daten["error"].get("code")
            if code in (-8504, -8998):
                meldung = ("Anmeldung abgelehnt. Schlüssel, Benutzername oder Schule prüfen "
                           "- oder die Systemuhr weicht zu stark ab (TOTP).")
            raise UntisFehler(meldung)
        return daten["result"]

    # -- Stammdaten --------------------------------------------------------

    def anmelden(self) -> str:
        """Meldet an und liefert den Anzeigenamen des Kontos."""
        ergebnis = self._rpc("getUserData2017", {"auth": self._auth()})
        self._stammdaten = ergebnis["masterData"]
        self._benutzer = ergebnis["userData"]
        return self._benutzer.get("displayName") or self.zugang.benutzer

    def _register(self, schluessel: str) -> dict[int, dict]:
        if self._stammdaten is None:
            raise UntisFehler("Nicht angemeldet.")
        return {eintrag["id"]: eintrag for eintrag in self._stammdaten.get(schluessel, [])}

    # -- Stundenplan -------------------------------------------------------

    def _perioden(self, typ: str, ident: int, von: dt.date, bis: dt.date) -> list[dict]:
        """Rohe Perioden eines Stundenplans (``STUDENT`` oder ``CLASS``)."""
        if self._benutzer is None or self._stammdaten is None:
            self.anmelden()
        assert self._stammdaten is not None

        ergebnis = self._rpc(
            "getTimetable2017",
            {
                "id": ident,
                "type": typ,
                "startDate": int(von.strftime("%Y%m%d")),
                "endDate": int(bis.strftime("%Y%m%d")),
                "masterDataTimestamp": self._stammdaten["timeStamp"],
                "timetableTimestamp": 0,
                "timetableTimestamps": [],
                "auth": self._auth(),
            },
        )
        return ergebnis.get("timetable", {}).get("periods", [])

    def stammklasse(self, stichtag: dt.date | None = None) -> int | None:
        """Ermittelt die Stammklasse aus dem eigenen Stundenplan.

        ``userData.klassenIds`` ist bei Schülerkonten leer, und gekoppelte
        Stunden nennen mehrere Klassen. Die mit Abstand häufigste über vier
        Wochen ist die Stammklasse.
        """
        if self._stammklasse is not None:
            return self._stammklasse
        if self._benutzer is None:
            self.anmelden()
        assert self._benutzer is not None

        montag = (stichtag or dt.date.today())
        montag -= dt.timedelta(days=montag.weekday())
        zaehler: collections.Counter[int] = collections.Counter()
        for woche in range(4):
            beginn = montag + dt.timedelta(weeks=woche)
            for periode in self._perioden(
                self._benutzer.get("elemType", "STUDENT"), self._benutzer["elemId"],
                beginn, beginn + dt.timedelta(days=6),
            ):
                for element in periode.get("elements", []):
                    if element["type"] == "CLASS" and element["id"] > 0:
                        zaehler[element["id"]] += 1
        self._stammklasse = zaehler.most_common(1)[0][0] if zaehler else None
        return self._stammklasse

    def termine(
        self,
        von: dt.date,
        bis: dt.date,
        modus: Modus = Modus.AENDERUNGEN,
    ) -> list[Termin]:
        """Holt den Stundenplan und fasst zusammenhängende Einheiten zusammen.

        Je nach ``modus`` wird der Klassenplan hinzugezogen. Der persönliche
        Plan hat dabei immer Vorrang; siehe :func:`_zusammenfuehren`.
        """
        if self._benutzer is None or self._stammdaten is None:
            self.anmelden()
        assert self._benutzer is not None and self._stammdaten is not None

        eigen = self._perioden(
            self._benutzer.get("elemType", "STUDENT"), self._benutzer["elemId"], von, bis
        )
        klasse: list[dict] = []
        if modus is not Modus.NUR_EIGEN and (klassen_id := self.stammklasse(von)):
            try:
                klasse = self._perioden("CLASS", klassen_id, von, bis)
            except UntisFehler:
                # Kein Zugriff auf den Klassenplan: lieber den eigenen Plan
                # zeigen als gar nichts.
                klasse = []

        register = {
            "subjects": self._register("subjects"),
            "teachers": self._register("teachers"),
            "rooms": self._register("rooms"),
            "klassen": self._register("klassen"),
        }
        return _zusammenfuehren(
            _zu_terminen(eigen, Quelle.EIGEN, register),
            _zu_terminen(klasse, Quelle.KLASSE, register),
            modus,
        )


def _zu_terminen(
    perioden: list[dict],
    quelle: Quelle,
    register: dict[str, dict[int, dict]],
) -> list[tuple[int, Termin]]:
    """Wandelt rohe Perioden in :class:`Termin`-Objekte samt ``lessonId``."""
    roh: list[tuple[int, Termin]] = []
    for periode in perioden:
        elemente: dict[str, list[dict]] = {}
        for element in periode.get("elements", []):
            elemente.setdefault(element["type"], []).append(element)

        def namen(typ: str, schluessel: str, feld: str = "name") -> str:
            gefunden = []
            for element in elemente.get(typ, []):
                eintrag = register[schluessel].get(element["id"]) or {}
                if wert := eintrag.get(feld):
                    gefunden.append(wert)
            # Untis liefert die Reihenfolge nicht stabil - sortieren, damit
            # derselbe Termin aus beiden Plänen gleich aussieht.
            return ", ".join(sorted(dict.fromkeys(gefunden)))

        zustaende = periode.get("is", [])
        text = periode.get("text") or {}
        # Untis wiederholt denselben Text gern in mehreren Feldern.
        hinweis = " \u00b7 ".join(
            dict.fromkeys(
                t.strip()
                for t in (text.get("substitution"), text.get("info"), text.get("lesson"))
                if t and t.strip()
            )
        )

        fach_eintrag = next(
            (register["subjects"].get(e["id"], {}) for e in elemente.get("SUBJECT", [])), {}
        )
        kuerzel = fach_eintrag.get("name", "")
        if kuerzel:
            fach, exakt = subjects.klartext(kuerzel, fach_eintrag.get("longName", ""))
        else:
            # Stunden ohne Gegenstand (Klassenvorstand, Fototermin, ...): Der
            # Begleittext ist hier die einzige Bezeichnung, und er ist keine
            # Abkürzung - also nicht als "abgeleitet" markieren.
            fach, exakt = (text.get("lesson") or hinweis or "ohne Gegenstand"), True

        roh.append((
            periode.get("lessonId", 0),
            Termin(
                beginn=dt.datetime.strptime(periode["startDateTime"].rstrip("Z"), _ZEITFORMAT),
                ende=dt.datetime.strptime(periode["endDateTime"].rstrip("Z"), _ZEITFORMAT),
                kuerzel=kuerzel,
                fach=fach,
                fach_exakt=exakt,
                lehrkraft=namen("TEACHER", "teachers", "lastName") or namen("TEACHER", "teachers"),
                raum=namen("ROOM", "rooms"),
                klasse=namen("CLASS", "klassen"),
                status=_status(zustaende),
                info=hinweis,
                entfaellt="CANCELLED" in zustaende,
                quelle=quelle,
            ),
        ))
    return roh


def _status(zustaende: list[str]) -> str:
    """Übersetzt die Zustandskennungen in eine kurze deutsche Beschriftung."""
    tabelle = {
        "CANCELLED": "Entfällt",
        "SUBSTITUTION": "Vertretung",
        "IRREGULAR": "Geändert",
        "ADDITIONAL": "Zusatzstunde",
        "SHIFT": "Verlegt",
        "ROOMSUBSTITUTION": "Raumänderung",
        "EXAM": "Prüfung",
        "EVENT": "Termin",
        "STANDBY": "Bereitschaft",
        "OFFICEHOUR": "Sprechstunde",
    }
    beschriftungen = [tabelle[z] for z in zustaende if z in tabelle]
    return ", ".join(beschriftungen) if beschriftungen else ""


#: Zustände, die eine Planänderung anzeigen - nur diese sind im Modus
#: AENDERUNGEN aus dem Klassenplan interessant.
_AENDERUNGS_ZUSTAENDE = frozenset({
    "Entfällt", "Vertretung", "Geändert", "Zusatzstunde", "Verlegt",
    "Raumänderung", "Prüfung", "Termin",
})


def _zusammenfuehren(
    eigen: list[tuple[int, Termin]],
    klasse: list[tuple[int, Termin]],
    modus: Modus,
) -> list[Termin]:
    """Führt persönlichen Plan und Klassenplan zusammen.

    Vorrang hat immer der persönliche Plan: Was dort steht, wird nie durch
    einen Klasseneintrag ersetzt oder doppelt gezeigt. Der Klassenplan ist
    eine Obermenge - er enthält auch Parallelgruppen (etwa Religion statt
    Ethik, Mädchen- statt Knabensport), die dieses Kind gar nicht besucht.
    Deshalb wird er gefiltert statt blind angehängt:

    * ``NUR_EIGEN``    - Klassenplan bleibt außen vor.
    * ``AENDERUNGEN``  - nur Einträge, die eine Änderung melden *und* ein Fach
      betreffen, das im eigenen Plan vorkommt.
    * ``KLASSE_VOLL``  - alles, was der eigene Plan nicht schon enthält.

    Meldet der Klassenplan für eine eigene Stunde einen anderen Status, gilt
    die Angabe der Klasse: Lehrkräfte tragen Änderungen dort zuerst ein.
    """
    # Räume sind sortiert, Zeiten identisch - damit ist der Schlüssel stabil.
    eigen_index: dict[tuple[int, dt.datetime, dt.datetime], Termin] = {
        (stunde, termin.beginn, termin.ende): termin for stunde, termin in eigen
    }
    eigene_faecher = {termin.kuerzel for _, termin in eigen if termin.kuerzel}

    def schon_belegt(termin: Termin) -> bool:
        """Hat er dasselbe Fach zur selben Zeit bereits im eigenen Plan?

        Der Klassenplan führt Teilungsgruppen als eigene Stunden mit eigener
        ``lessonId``. Ohne diese Prüfung stünde etwa Ethik zweimal da - einmal
        seine Gruppe, einmal die der Parallelgruppe.
        """
        return any(
            anderer.kuerzel == termin.kuerzel
            and anderer.beginn < termin.ende
            and termin.beginn < anderer.ende
            for _, anderer in eigen
        )

    zusatz: list[tuple[int, Termin]] = []
    for stunde, termin in klasse:
        vorhanden = eigen_index.get((stunde, termin.beginn, termin.ende))
        if vorhanden is not None:
            if termin.status != vorhanden.status:
                vorhanden.klassen_hinweis = (
                    f"Klassenplan meldet: {termin.status or 'regulär'}"
                )
                vorhanden.status = termin.status or vorhanden.status
                vorhanden.entfaellt = termin.entfaellt
            continue

        if schon_belegt(termin):
            continue

        if modus is Modus.KLASSE_VOLL:
            zusatz.append((stunde, termin))
        elif modus is Modus.AENDERUNGEN:
            meldet_aenderung = any(
                teil.strip() in _AENDERUNGS_ZUSTAENDE for teil in termin.status.split(",")
            )
            if meldet_aenderung and termin.kuerzel in eigene_faecher:
                zusatz.append((stunde, termin))

    return _zusammenfassen(eigen + zusatz)


def _zusammenfassen(roh: list[tuple[int, Termin]]) -> list[Termin]:
    """Fasst direkt aufeinanderfolgende Einheiten derselben Stunde zusammen.

    WebUntis liefert Doppelstunden als zwei getrennte Einträge; für die Anzeige
    ist ein Block von 08:15 bis 09:55 leserlicher als zwei Zeilen.
    """
    roh.sort(key=lambda paar: (paar[1].beginn, paar[1].kuerzel))
    zusammengefasst: list[Termin] = []
    # Schlüssel enthält die Quelle, damit ein Klasseneintrag nie mit einem
    # eigenen Eintrag zu einem Block verschmilzt.
    letzte_stunde: dict[tuple[int, Quelle], Termin] = {}

    for stunden_id, termin in roh:
        gruppe = (stunden_id, termin.quelle)
        vorheriger = letzte_stunde.get(gruppe)
        passt = (
            vorheriger is not None
            and stunden_id
            and vorheriger.ende == termin.beginn
            and vorheriger.raum == termin.raum
            and vorheriger.status == termin.status
        )
        if passt and vorheriger is not None:
            vorheriger.ende = termin.ende
            continue
        zusammengefasst.append(termin)
        letzte_stunde[gruppe] = termin

    zusammengefasst.sort(key=lambda t: (t.beginn, t.kuerzel))
    return zusammengefasst
