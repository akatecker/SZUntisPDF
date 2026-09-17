"""Einstiegspunkt: Server starten, Browser öffnen, laufen lassen."""

from __future__ import annotations

import os
import sys
import threading
import webbrowser

from . import server as webserver


def main() -> int:
    server, zustand = webserver.starten()
    adresse = f"http://127.0.0.1:{server.server_port}/?s={zustand.geheimnis}"

    # Gespeichertes Konto übernehmen, damit nicht jedes Mal gescannt werden muss.
    gefunden = zustand.aus_ablage_laden()

    # flush: Im gepackten Programm ist die Ausgabe blockgepuffert, sonst
    # erscheint die Adresse erst beim Beenden.
    print("SZUntisPDF läuft.", flush=True)
    print(f"  Oberfläche: {adresse}", flush=True)
    print("  Konto     :", zustand.name if gefunden else "noch nicht eingerichtet", flush=True)
    print("  Beenden   : dieses Fenster schließen oder Strg+C", flush=True)

    # In Bauläufen und Tests soll kein Browser aufgehen.
    if not os.environ.get("SZUNTIS_KEIN_BROWSER"):
        threading.Timer(0.4, lambda: webbrowser.open(adresse)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
