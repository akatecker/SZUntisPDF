package io.github.akatecker.szuntispdf

import android.content.Context
import org.json.JSONObject

/**
 * Legt den Zugang im privaten Bereich der App ab.
 *
 * Der Ordner gehört allein dieser App; andere Apps kommen ohne Root nicht
 * heran. Beim Deinstallieren verschwindet er mit.
 */
object Konto {

    private const val DATEI = "konto.json"

    fun laden(zusammenhang: Context): Zugang? {
        val datei = zusammenhang.filesDir.resolve(DATEI)
        if (!datei.exists()) return null
        return try {
            val werte = JSONObject(datei.readText(Charsets.UTF_8))
            Zugang(
                server = werte.optString("server"),
                schule = werte.optString("schule"),
                benutzer = werte.optString("benutzer"),
                schluessel = werte.optString("schluessel"),
            ).takeIf { it.vollstaendig }
        } catch (_: Exception) {
            null   // beschädigt - dann eben neu einrichten
        }
    }

    fun speichern(zusammenhang: Context, zugang: Zugang) {
        val inhalt = JSONObject()
            .put("server", zugang.server)
            .put("schule", zugang.schule)
            .put("benutzer", zugang.benutzer)
            .put("schluessel", zugang.schluessel)
            .toString(1)
        zusammenhang.filesDir.resolve(DATEI).writeText(inhalt, Charsets.UTF_8)
    }

    fun loeschen(zusammenhang: Context) {
        zusammenhang.filesDir.resolve(DATEI).delete()
    }
}
