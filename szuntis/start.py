"""Öffnet die Oberfläche so, dass sie wie ein eigenes Programm wirkt.

Chromium-Browser kennen den Schalter ``--app=``: Das öffnet ein Fenster ohne
Adresszeile, ohne Tableiste, mit eigenem Eintrag im Dock bzw. in der
Taskleiste und dem Symbol der Seite - also dem Schullogo. Von einem
Fensterprogramm ist das kaum zu unterscheiden.

Ist kein solcher Browser da, wird der Standardbrowser genommen. Dann ist es
ein gewöhnlicher Tab, aber es funktioniert.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import webbrowser

#: Kandidaten je Plattform, in der Reihenfolge der Bevorzugung.
_CHROMIUM = {
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "win32": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "linux": ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"],
}


def _chromium_finden() -> str | None:
    for pfad in _CHROMIUM.get(sys.platform, _CHROMIUM["linux"]):
        if pathlib.Path(pfad).exists():
            return pfad
    return None


def _saubere_umgebung() -> dict[str, str]:
    """Umgebung ohne die Spuren des PyInstaller-Laders.

    Ein gepacktes Programm setzt ``DYLD_LIBRARY_PATH`` und Verwandte auf sein
    Entpackverzeichnis. Erbt der Browser das, findet er falsche Bibliotheken
    und startet gar nicht erst. PyInstaller hebt die urspruenglichen Werte
    unter ``..._ORIG`` auf.
    """
    umgebung = dict(os.environ)
    for name in ("DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "DYLD_INSERT_LIBRARIES",
                 "LD_LIBRARY_PATH"):
        vorher = umgebung.pop(name + "_ORIG", None)
        if vorher:
            umgebung[name] = vorher
        else:
            umgebung.pop(name, None)
    return umgebung


def _profilordner() -> pathlib.Path:
    """Eigener Browser-Profilordner.

    Ohne ihn würde ``--app`` in einer schon laufenden Browsersitzung landen und
    beim Schließen des Hauptfensters mit verschwinden. Ein eigenes Profil macht
    das Fenster unabhängig - und hält die Sitzung von der des Benutzers getrennt.
    """
    from . import konto

    ordner = konto.ablageordner() / "fenster"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def oberflaeche_oeffnen(adresse: str) -> str:
    """Öffnet die Adresse und meldet zurück, auf welchem Weg."""
    if os.environ.get("SZUNTIS_KEIN_BROWSER"):
        return "nicht geöffnet (SZUNTIS_KEIN_BROWSER gesetzt)"

    browser = _chromium_finden()
    if browser:
        try:
            subprocess.Popen(
                [
                    browser,
                    f"--app={adresse}",
                    f"--user-data-dir={_profilordner()}",
                    "--window-size=1280,860",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_saubere_umgebung(),
                start_new_session=True,
            )
            return f"eigenes Fenster ({pathlib.Path(browser).stem})"
        except OSError:
            pass  # dann eben der Standardweg

    webbrowser.open(adresse)
    return "Standardbrowser"
