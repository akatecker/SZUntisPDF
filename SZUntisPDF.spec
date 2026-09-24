# PyInstaller-Bauplan fuer macOS und Windows.
#
# Aufruf:  pyinstaller --noconfirm SZUntisPDF.spec
#
# Bewusst OHNE Konsolenfenster: Die Oberflaeche ist das Programm. Beendet wird,
# indem man ihr Fenster schliesst - sie schickt Lebenszeichen, und bleiben die
# aus, macht das Programm von selbst Schluss. Die Adresse steht zusaetzlich in
# adresse.txt im Anwendungsordner, falls sich kein Fenster oeffnet.

import sys
from pathlib import Path

WURZEL = Path(SPECPATH)

def fassung() -> str:
    """Versionsnummer aus dem Git-Tag, sonst aus der Umgebung.

    Fest eingetragen wurde sie schon einmal vergessen: Das 1.3.0-Release trug
    im Buendel noch 1.2.0.
    """
    import os
    import subprocess

    if wert := os.environ.get("SZUNTIS_VERSION"):
        return wert.lstrip("v")
    try:
        roh = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=SPECPATH, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        roh = ""
    # CFBundleVersion vertraegt nur Ziffern und Punkte.
    ziffern = ".".join(t for t in roh.lstrip("v").split(".") if t.isdigit())
    return ziffern or "0.0.0"


VERSION = fassung()

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
    console=False,
    icon=symbol,
    upx=False,          # bringt bei Python-Paketen kaum etwas und stoert Virenscanner
    strip=sys.platform != "win32",
    onefile=True,
)

if sys.platform == "darwin":
    # Erst ein .app-Buendel macht aus dem Binaer ein richtiges Programm:
    # Symbol im Finder, Eintrag im Dock, ordentlicher Name.
    app = BUNDLE(
        exe,
        name="SZUntisPDF.app",
        icon=symbol,
        bundle_identifier="io.github.akatecker.szuntispdf",
        info_plist={
            "CFBundleName": "SZUntisPDF",
            "CFBundleDisplayName": "SZUntisPDF",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.education",
            # Kein Fenster von uns selbst - die Oberflaeche laeuft im Browser.
            "LSBackgroundOnly": False,
        },
    )
