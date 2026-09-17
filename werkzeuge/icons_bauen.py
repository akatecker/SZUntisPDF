"""Erzeugt aus dem Schullogo die Programmsymbole fuer macOS und Windows.

Aufruf:  python3 werkzeuge/icons_bauen.py
Braucht Pillow; die fertigen Symbole liegen im Repo, damit die Bauläufe
in der Continuous Integration keine Bildbibliothek brauchen.
"""

import pathlib
import subprocess
import sys

from PIL import Image

WURZEL = pathlib.Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "assets" / "szu-logo.jpg"
ZIEL = WURZEL / "assets"


def signet(bild: Image.Image) -> Image.Image:
    """Loest das farbige Signet aus dem Banner.

    Ein rechteckiger Zuschnitt genuegt nicht: Der blaue Bogen reicht weiter
    nach rechts als der Anfang der Wortmarke. Stattdessen bleiben nur kraeftig
    gesaettigte Pixel stehen - die Schrift ist dunkelgrau und faellt weg.
    """
    roh = bild.crop((0, 0, 215, bild.height)).convert("RGB")  # vor dem farbigen Untertitel
    punkte = roh.load()

    def gesaettigt(x, y):
        r, g, b = punkte[x, y]
        return max(r, g, b) > 80 and (max(r, g, b) - min(r, g, b)) > 60

    maske = Image.new("RGB", roh.size, "white")
    setzen = maske.load()
    spalten, zeilen = [], []
    for x in range(roh.width):
        for y in range(roh.height):
            if gesaettigt(x, y):
                setzen[x, y] = punkte[x, y]
                spalten.append(x)
                zeilen.append(y)
    return maske.crop((min(spalten), min(zeilen), max(spalten) + 1, max(zeilen) + 1))


def quadrat(mark: Image.Image, kante: int = 1024, rand: float = 0.14) -> Image.Image:
    """Legt das Signet mittig auf eine weisse quadratische Flaeche."""
    platz = int(kante * (1 - 2 * rand))
    faktor = min(platz / mark.width, platz / mark.height)
    skaliert = mark.resize((round(mark.width * faktor), round(mark.height * faktor)), Image.LANCZOS)
    flaeche = Image.new("RGB", (kante, kante), "white")
    flaeche.paste(skaliert, ((kante - skaliert.width) // 2, (kante - skaliert.height) // 2))
    return flaeche


def main() -> int:
    if not QUELLE.exists():
        print(f"Logo fehlt: {QUELLE}", file=sys.stderr)
        return 1

    gross = quadrat(signet(Image.open(QUELLE)))
    gross.save(ZIEL / "icon.png")

    # Windows: mehrere Groessen in einer Datei.
    gross.save(ZIEL / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

    # macOS: iconset-Ordner, dann von iconutil einpacken lassen.
    if sys.platform == "darwin":
        satz = ZIEL / "icon.iconset"
        satz.mkdir(exist_ok=True)
        for kante in (16, 32, 64, 128, 256, 512, 1024):
            gross.resize((kante, kante), Image.LANCZOS).save(satz / f"icon_{kante}x{kante}.png")
            if kante <= 512:
                gross.resize((kante * 2, kante * 2), Image.LANCZOS).save(satz / f"icon_{kante}x{kante}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(satz), "-o", str(ZIEL / "icon.icns")], check=True)
        for datei in satz.iterdir():
            datei.unlink()
        satz.rmdir()

    for name in ("icon.png", "icon.ico", "icon.icns"):
        pfad = ZIEL / name
        if pfad.exists():
            print(f"  {name:11} {pfad.stat().st_size / 1024:7.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
