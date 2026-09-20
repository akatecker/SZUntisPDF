"""Prueft ein frisch gebautes Programm, ohne Zugangsdaten zu brauchen.

Startet die Datei, liest die Adresse aus der Ausgabe, holt die Oberflaeche und
die Statusabfrage ab und beendet wieder. Faengt genau die Fehler, die beim
Packen typisch sind: fehlende Oberflaechendateien, kaputte Importe, nicht
startender Server.

Aufruf:  python werkzeuge/rauchtest.py dist/SZUntisPDF
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

WARTEZEIT = 60


def _adressdatei() -> pathlib.Path:
    """Dieselbe Stelle, an die das Programm seine Adresse schreibt."""
    if sys.platform == "win32":
        basis = pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        basis = pathlib.Path.home() / "Library" / "Application Support"
    else:
        basis = pathlib.Path(os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config"))
    return basis / "SZUntisPDF" / "adresse.txt"


def main(pfad: str, tls_pruefen: bool = False) -> int:
    if not os.path.exists(pfad):
        print(f"FEHLER: {pfad} gibt es nicht", file=sys.stderr)
        return 1

    umgebung = dict(os.environ, BROWSER="true", SZUNTIS_KEIN_BROWSER="1")
    adressdatei = _adressdatei()
    adressdatei.unlink(missing_ok=True)
    prozess = subprocess.Popen(
        [pfad], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=umgebung
    )

    # Als Fensterprogramm gepackt gibt es keine Konsolenausgabe mehr; die
    # Adresse holen wir deshalb aus der Datei, die das Programm schreibt.
    port = schluessel = None
    grenze = time.time() + WARTEZEIT
    while time.time() < grenze:
        if prozess.poll() is not None:
            print("FEHLER: Das Programm hat sich sofort beendet.", file=sys.stderr)
            print(prozess.stdout.read(), file=sys.stderr)
            return 1
        if adressdatei.exists():
            treffer = re.search(r"http://127\.0\.0\.1:(\d+)/\?s=(\S+)",
                                adressdatei.read_text(encoding="utf-8"))
            if treffer:
                port, schluessel = treffer.group(1), treffer.group(2)
                print(f"    Adresse aus {adressdatei.name}: Port {port}")
                break
        time.sleep(0.5)

    if not port:
        prozess.kill()
        print("FEHLER: Das Programm hat keine Adresse hinterlegt.", file=sys.stderr)
        return 1

    basis = f"http://127.0.0.1:{port}"
    fehler = 0
    try:
        for datei, mindestens in (("/", 500), ("/app.js", 2000), ("/stil.css", 1000),
                                  ("/jsqr.js", 10000), ("/logo.jpg", 1000)):
            with urllib.request.urlopen(basis + datei, timeout=20) as antwort:
                groesse = len(antwort.read())
            zeichen = "ok" if groesse >= mindestens else "ZU KLEIN"
            print(f"    {datei:12} {groesse:7d} Bytes  {zeichen}")
            fehler += groesse < mindestens

        anfrage = urllib.request.Request(
            basis + "/api/status", headers={"X-SZU-Schluessel": schluessel}
        )
        with urllib.request.urlopen(anfrage, timeout=20) as antwort:
            status = json.loads(antwort.read())
        print(f"    /api/status  angemeldet={status['angemeldet']} "
              f"modi={len(status.get('modi', []))}")
        if len(status.get("modi", [])) != 3:
            print("FEHLER: Betriebsarten unvollständig", file=sys.stderr)
            fehler += 1

        if tls_pruefen:
            # Ein gepacktes Programm ohne Zertifikatsspeicher startet zwar,
            # kann aber keine einzige Verbindung zu WebUntis aufbauen.
            anzahl = status.get("tlsZertifikate", 0)
            print(f"    Wurzelzertifikate: {anzahl}")
            if anzahl < 10:
                print("FEHLER: Kein Zertifikatsspeicher im Paket - HTTPS würde "
                      "mit CERTIFICATE_VERIFY_FAILED scheitern.", file=sys.stderr)
                fehler += 1

        # Ohne Schluessel muss die Schnittstelle dichtmachen.
        try:
            urllib.request.urlopen(basis + "/api/status", timeout=20)
            print("FEHLER: Schnittstelle antwortet ohne Schlüssel", file=sys.stderr)
            fehler += 1
        except urllib.error.HTTPError as abweisung:
            print(f"    ohne Schlüssel: {abweisung.code} (erwartet 403)")
            fehler += abweisung.code != 403
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=15)
        except subprocess.TimeoutExpired:
            prozess.kill()

    print("Rauchtest bestanden." if not fehler else f"Rauchtest: {fehler} Beanstandung(en).")
    return 1 if fehler else 0


if __name__ == "__main__":
    argumente = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(argumente) != 1:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(argumente[0], tls_pruefen="--tls" in sys.argv))
