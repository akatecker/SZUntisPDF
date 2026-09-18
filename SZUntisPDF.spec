# PyInstaller-Bauplan fuer macOS und Windows.
#
# Aufruf:  pyinstaller --noconfirm SZUntisPDF.spec
#
# Bewusst als Konsolenprogramm: Das Fenster zeigt die Adresse der Oberflaeche,
# falls sich der Browser nicht von selbst oeffnet, und das Schliessen des
# Fensters beendet das Programm. Ohne Konsole gaebe es unter Windows keinen
# Weg, es wieder loszuwerden.

import sys
from pathlib import Path

WURZEL = Path(SPECPATH)

symbol = None
for kandidat in (("icon.icns" if sys.platform == "darwin" else "icon.ico"),):
    pfad = WURZEL / "assets" / kandidat
    if pfad.exists():
        symbol = str(pfad)

analyse = Analysis(
    [str(WURZEL / "start.py")],
    pathex=[str(WURZEL)],
    datas=[(str(WURZEL / "szuntis" / "web"), "web")],
    # certifi liefert den Zertifikatsspeicher mit. Ohne ihn scheitert im
    # gepackten Programm jede HTTPS-Verbindung an CERTIFICATE_VERIFY_FAILED.
    hiddenimports=["szuntis", "szuntis.server", "szuntis.untis", "szuntis.subjects",
                   "szuntis.konto", "certifi"],
    # Alles raus, was ein Stundenplan nicht braucht. Spart rund 3 MB.
    excludes=[
        "tkinter", "unittest", "pydoc", "doctest", "test", "distutils",
        "lib2to3", "sqlite3", "xml", "xmlrpc", "pdb", "difflib",
        "multiprocessing", "asyncio", "concurrent", "decimal", "pickletools",
        "numpy", "cv2", "PIL", "PySide6", "requests",
    ],
    noarchive=False,
)

archiv = PYZ(analyse.pure)

exe = EXE(
    archiv,
    analyse.scripts,
    analyse.binaries,
    analyse.datas,
    [],
    name="SZUntisPDF",
    console=True,
    icon=symbol,
    upx=False,          # bringt bei Python-Paketen kaum etwas und stoert Virenscanner
    strip=sys.platform != "win32",
    onefile=True,
)
