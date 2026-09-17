"""Startpunkt fuer das gepackte Programm.

PyInstaller fuehrt das Startskript als eigenstaendiges Modul aus; relative
Importe wie in ``szuntis/__main__.py`` funktionieren dort nicht. Deshalb dieser
duenne Umweg ueber den normalen Paketimport.
"""

from szuntis.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
