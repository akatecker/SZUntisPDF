"""Erzeugt die Kotlin-Fassung der Faecherliste aus szuntis/subjects.py.

Eine Quelle, zwei Ziele: Die Liste wird aus der PDF der Schule erzeugt und
darf nicht an zwei Stellen von Hand gepflegt werden.

Aufruf:  python3 werkzeuge/faecher_nach_kotlin.py
"""

import pathlib
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from szuntis import subjects  # noqa: E402

ZIEL = WURZEL / "android/app/src/main/java/io/github/akatecker/szuntispdf/Faecher.kt"


def kotlin_text(wert: str) -> str:
    return '"' + wert.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$") + '"'


def main() -> int:
    eintraege = "\n".join(
        f"    {kotlin_text(abk)} to {kotlin_text(text)},"
        for abk, text in sorted(subjects.FAECHER.items())
    )

    ZIEL.write_text(f'''package io.github.akatecker.szuntispdf

/**
 * Fächerabkürzungen des Schulzentrums Ungargasse (Schuljahr 2026/27).
 *
 * Automatisch erzeugt von `werkzeuge/faecher_nach_kotlin.py` aus
 * `szuntis/subjects.py`. Nicht von Hand bearbeiten.
 */
object Faecher {{

    val liste: Map<String, String> = mapOf(
{eintraege}
    )

    /** Entfernt Jahrgangs- und Variantenkennungen: `FET2_1` -> `FET`, `NW2` -> `NW`. */
    private fun stamm(abkuerzung: String): String =
        abkuerzung.replace(Regex("_\\\\d+[A-Z]?$"), "").replace(Regex("\\\\d+$"), "")

    /** Stammform -> Bezeichnung, aber nur wo eindeutig (FET/NWT/UFW sind es nicht). */
    private val stammIndex: Map<String, String> =
        liste.entries.groupBy {{ stamm(it.key) }}
            .mapValues {{ (_, treffer) -> treffer.map {{ it.value }}.distinct() }}
            .filterValues {{ it.size == 1 }}
            .mapValues {{ it.value.first() }}

    /**
     * Löst eine Fächerabkürzung in Klartext auf.
     *
     * Zweiter Wert ist `false`, wenn die Bezeichnung über die Stammform
     * abgeleitet wurde oder aus dem WebUntis-Langnamen stammt.
     */
    fun klartext(abkuerzung: String?, ersatz: String = ""): Pair<String, Boolean> {{
        val kurz = abkuerzung?.trim().orEmpty()
        if (kurz.isEmpty()) return (ersatz to false)
        liste[kurz]?.let {{ return it to true }}
        stammIndex[stamm(kurz)]?.let {{ return it to false }}
        if (ersatz.isNotEmpty()) {{
            val geglaettet = if (ersatz == ersatz.uppercase()) {{
                ersatz.lowercase().replaceFirstChar {{ it.uppercase() }}
            }} else ersatz
            return geglaettet to false
        }}
        return kurz to false
    }}
}}
''', encoding="utf-8")

    print(f"{ZIEL.relative_to(WURZEL)}: {len(subjects.FAECHER)} Einträge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
