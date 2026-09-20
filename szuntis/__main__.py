"""Einstiegspunkt: Server starten, Oberfläche öffnen, aufräumen.

Läuft ohne Konsolenfenster. Beendet wird nicht über ein Terminal, sondern
indem das Fenster geschlossen wird: Die Oberfläche schickt regelmäßig ein
Lebenszeichen, und bleibt es aus, macht das Programm von selbst Schluss.
"""

from __future__ import annotations

import pathlib
import signal
import sys
import threading
import time

from . import konto as kontoablage
from . import server as webserver
from . import start as starthilfe

#: Wie oft der Wächter nachsieht. Die Geduld selbst steht im Zustand, damit
#: der Server sie beim Fensterschließen verkürzen kann.
_PRUEFABSTAND = 2


def melde(text: str) -> None:
    """Ausgabe, die auch ohne Konsole nicht stört.

    Als Fensterprogramm gepackt gibt es kein ``stdout``; ein schlichtes
    ``print`` liefe dort auf die Nase.
    """
    if sys.stdout is not None:
        try:
            print(text, flush=True)
        except (OSError, ValueError):
            pass


def _adressdatei() -> pathlib.Path:
    """Hier steht die Adresse der Oberfläche, solange das Programm läuft.

    Nützlich, wenn sich kein Fenster geöffnet hat - und der einzige Weg für
    den Rauchtest, das gepackte Programm ohne Konsole zu erreichen.
    """
    ordner = kontoablage.ablageordner()
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner / "adresse.txt"


def _wache(zustand: webserver.Zustand) -> None:
    """Beendet das Programm, wenn sich die Oberfläche nicht mehr meldet."""
    while not zustand.schluss.wait(_PRUEFABSTAND):
        if time.monotonic() - zustand.letztes_lebenszeichen > zustand.geduld:
            zustand.schluss.set()
            return


def main() -> int:
    server, zustand = webserver.starten()
    adresse = f"http://127.0.0.1:{server.server_port}/?s={zustand.geheimnis}"

    bediener = threading.Thread(target=server.serve_forever, daemon=True)
    bediener.start()

    # Gespeichertes Konto übernehmen, damit nicht jedes Mal gescannt werden muss.
    # Erst hinterlegen, dann oeffnen: Die Adresse muss auch dann auffindbar
    # sein, wenn sich kein Fenster oeffnen laesst.
    try:
        _adressdatei().write_text(adresse + "\n", encoding="utf-8")
    except OSError:
        pass

    gefunden = zustand.aus_ablage_laden()
    weg = starthilfe.oberflaeche_oeffnen(adresse)

    # Nur sichtbar, wenn jemand das Programm aus einem Terminal startet.
    melde("SZUntisPDF läuft.")
    melde(f"  Oberfläche: {adresse}")
    melde(f"  Geöffnet  : {weg}")
    melde("  Konto     : " + (zustand.name if gefunden else "noch nicht eingerichtet"))
    melde("  Beenden   : Fenster schließen")

    for zeichen in (signal.SIGINT, signal.SIGTERM):
        signal.signal(zeichen, lambda *_: zustand.schluss.set())

    threading.Thread(target=_wache, args=(zustand,), daemon=True).start()

    try:
        zustand.schluss.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        _adressdatei().unlink(missing_ok=True)
    melde("Beendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
