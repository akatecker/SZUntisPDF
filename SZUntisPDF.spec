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
            "CFBundleShortVersionString": "1.2.0",
            "CFBundleVersion": "1.2.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.education",
            # Kein Fenster von uns selbst - die Oberflaeche laeuft im Browser.
            "LSBackgroundOnly": False,
        },
    )
