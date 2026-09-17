"""Speichert die Zugangsdaten im Benutzerprofil.

Bewusst nicht im Programmordner: Das Programm selbst soll weitergegeben werden
können, ohne dass ein fremdes Konto mitwandert.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

from .untis import Zugang

_ORDNERNAME = "SZUntisPDF"


def ablageordner() -> pathlib.Path:
    """Plattformüblicher Ort für Anwendungsdaten."""
    if sys.platform == "win32":
        basis = pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        basis = pathlib.Path.home() / "Library" / "Application Support"
    else:
        basis = pathlib.Path(os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config"))
    return basis / _ORDNERNAME


def _datei() -> pathlib.Path:
    return ablageordner() / "konto.json"


def laden() -> Zugang | None:
    """Liest das gespeicherte Konto, oder ``None`` wenn keines hinterlegt ist."""
    datei = _datei()
    if not datei.exists():
        return None
    try:
        werte = json.loads(datei.read_text(encoding="utf-8"))
        zugang = Zugang(
            server=werte["server"],
            schule=werte["schule"],
            benutzer=werte["benutzer"],
            schluessel=werte["schluessel"],
        )
    except (ValueError, KeyError, OSError):
        return None  # beschädigt - dann eben neu einrichten
    return zugang if all(dataclass_werte(zugang)) else None


def dataclass_werte(zugang: Zugang) -> tuple[str, str, str, str]:
    return (zugang.server, zugang.schule, zugang.benutzer, zugang.schluessel)


def speichern(zugang: Zugang) -> pathlib.Path:
    """Legt das Konto ab - nur für den eigenen Benutzer lesbar."""
    ordner = ablageordner()
    ordner.mkdir(parents=True, exist_ok=True)
    datei = _datei()
    datei.write_text(
        json.dumps(
            {
                "server": zugang.server,
                "schule": zugang.schule,
                "benutzer": zugang.benutzer,
                "schluessel": zugang.schluessel,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    if sys.platform != "win32":
        datei.chmod(0o600)
    return datei


def loeschen() -> None:
    """Entfernt das gespeicherte Konto."""
    _datei().unlink(missing_ok=True)
