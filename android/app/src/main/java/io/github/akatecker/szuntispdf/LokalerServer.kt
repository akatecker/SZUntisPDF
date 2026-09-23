package io.github.akatecker.szuntispdf

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.security.SecureRandom
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.concurrent.Executors

/**
 * Kleiner HTTP-Server auf 127.0.0.1, der die WebView bedient.
 *
 * Warum überhaupt ein Server in einer App: Die Oberfläche ist dieselbe wie auf
 * dem Desktop und spricht über `fetch("/api/...")`. Eine WebView setzt CORS
 * durch, könnte WebUntis also nicht direkt ansprechen - die Netzwerkaufrufe
 * müssen ohnehin durch nativen Code. Mit diesem Server bleibt die getestete
 * Oberfläche Zeichen für Zeichen dieselbe.
 *
 * Gebunden wird ausschließlich an die Loopback-Adresse, und jede Anfrage an
 * `/api/` muss das beim Start erzeugte Geheimnis mitbringen.
 */
class LokalerServer(private val zusammenhang: Context) {

    val geheimnis: String = erzeugeGeheimnis()
    private var buchse: ServerSocket? = null
    private val arbeiter = Executors.newFixedThreadPool(4)

    @Volatile private var konto: UntisKonto? = null

    /**
     * Ein von aussen hereingereichter QR-Code (Scan mit einer beliebigen
     * Kamera-App). Die Oberflaeche holt ihn beim naechsten Statusabruf ab.
     */
    @Volatile var wartenderCode: String? = null

    val port: Int get() = buchse?.localPort ?: 0
    val adresse: String get() = "http://127.0.0.1:$port/?s=$geheimnis"

    // -- Lebenszyklus ------------------------------------------------------

    fun starten() {
        val server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        buchse = server
        Thread({
            while (!server.isClosed) {
                val verbindung = try {
                    server.accept()
                } catch (_: Exception) {
                    break
                }
                arbeiter.execute { bedienen(verbindung) }
            }
        }, "szu-server").apply { isDaemon = true }.start()
    }

    fun beenden() {
        try { buchse?.close() } catch (_: Exception) { }
        arbeiter.shutdownNow()
    }

    /** Übernimmt ein gespeichertes Konto. Liefert `true`, wenn es klappt. */
    fun ausAblageLaden(): Boolean {
        val zugang = Konto.laden(zusammenhang) ?: return false
        return try {
            UntisKonto(zugang).also { it.anmelden(); konto = it }
            true
        } catch (_: UntisFehler) {
            false
        }
    }

    private fun erzeugeGeheimnis(): String {
        val roh = ByteArray(18)
        SecureRandom().nextBytes(roh)
        return roh.joinToString("") { "%02x".format(it) }
    }

    // -- HTTP --------------------------------------------------------------

    private fun bedienen(verbindung: Socket) {
        verbindung.use { draht ->
            val leser = BufferedReader(InputStreamReader(draht.getInputStream(), Charsets.UTF_8))
            val startzeile = leser.readLine() ?: return
            val teile = startzeile.split(" ")
            if (teile.size < 2) return
            val verfahren = teile[0]
            val ziel = teile[1]

            val kopfzeilen = HashMap<String, String>()
            while (true) {
                val zeile = leser.readLine() ?: break
                if (zeile.isEmpty()) break
                val trenn = zeile.indexOf(':')
                if (trenn > 0) {
                    kopfzeilen[zeile.substring(0, trenn).trim().lowercase()] =
                        zeile.substring(trenn + 1).trim()
                }
            }

            val laenge = kopfzeilen["content-length"]?.toIntOrNull() ?: 0
            val rumpf = if (laenge > 0) {
                CharArray(laenge).let { puffer ->
                    var gelesen = 0
                    while (gelesen < laenge) {
                        val jetzt = leser.read(puffer, gelesen, laenge - gelesen)
                        if (jetzt < 0) break
                        gelesen += jetzt
                    }
                    String(puffer, 0, gelesen)
                }
            } else ""

            val pfad = ziel.substringBefore('?')
            val abfrage = ziel.substringAfter('?', "")
            val strom = draht.getOutputStream()

            if (pfad.startsWith("/api/")) {
                if (!zugelassen(kopfzeilen)) {
                    return sendeJson(strom, 403, JSONObject().put("fehler", "Nicht zugelassen."))
                }
                schnittstelle(strom, verfahren, pfad, abfrage, rumpf)
            } else {
                dateiAusliefern(strom, pfad)
            }
        }
    }

    private fun zugelassen(kopfzeilen: Map<String, String>): Boolean {
        val gastgeber = kopfzeilen["host"]?.substringBefore(':')
        if (gastgeber != "127.0.0.1" && gastgeber != "localhost") return false
        val mitgeschickt = kopfzeilen["x-szu-schluessel"].orEmpty()
        // Zeitkonstanter Vergleich
        if (mitgeschickt.length != geheimnis.length) return false
        var abweichung = 0
        for (i in geheimnis.indices) abweichung = abweichung or
            (geheimnis[i].code xor mitgeschickt[i].code)
        return abweichung == 0
    }

    private fun senden(strom: OutputStream, code: Int, inhalt: ByteArray, typ: String) {
        val zustand = when (code) {
            200 -> "OK"; 403 -> "Forbidden"; 404 -> "Not Found"
            409 -> "Conflict"; 502 -> "Bad Gateway"; else -> "Error"
        }
        val kopf = buildString {
            append("HTTP/1.1 $code $zustand\r\n")
            append("Content-Type: $typ\r\n")
            append("Content-Length: ${inhalt.size}\r\n")
            append("Cache-Control: no-store\r\n")
            append("X-Content-Type-Options: nosniff\r\n")
            append("Connection: close\r\n\r\n")
        }
        strom.write(kopf.toByteArray(Charsets.UTF_8))
        strom.write(inhalt)
        strom.flush()
    }

    private fun sendeJson(strom: OutputStream, code: Int, daten: JSONObject) =
        senden(strom, code, daten.toString().toByteArray(Charsets.UTF_8),
               "application/json; charset=utf-8")

    // -- Oberflächendateien ------------------------------------------------

    private fun dateiAusliefern(strom: OutputStream, pfad: String) {
        val name = if (pfad == "/" || pfad.isEmpty()) "index.html" else pfad.trimStart('/')
        if (name.contains("..")) {
            return senden(strom, 404, "Nicht gefunden".toByteArray(), "text/plain; charset=utf-8")
        }
        try {
            val inhalt = zusammenhang.assets.open("web/$name").use { it.readBytes() }
            senden(strom, 200, inhalt, typZu(name))
        } catch (_: Exception) {
            senden(strom, 404, "Nicht gefunden".toByteArray(), "text/plain; charset=utf-8")
        }
    }

    private fun typZu(name: String) = when (name.substringAfterLast('.', "")) {
        "html" -> "text/html; charset=utf-8"
        "css" -> "text/css; charset=utf-8"
        "js" -> "text/javascript; charset=utf-8"
        "json" -> "application/json; charset=utf-8"
        "jpg", "jpeg" -> "image/jpeg"
        "png" -> "image/png"
        "svg" -> "image/svg+xml"
        else -> "application/octet-stream"
    }

    // -- Schnittstelle -----------------------------------------------------

    private fun schnittstelle(
        strom: OutputStream, verfahren: String, pfad: String,
        abfrage: String, rumpf: String,
    ) {
        when {
            pfad == "/api/status" && verfahren == "GET" -> {
                val angemeldet = konto != null
                sendeJson(strom, 200, JSONObject()
                    .put("angemeldet", angemeldet)
                    .put("name", konto?.anzeigename.orEmpty())
                    .put("benutzer", konto?.zugang?.benutzer.orEmpty())
                    .put("schule", konto?.zugang?.schule.orEmpty())
                    .put("modi", JSONArray(Modus.entries.map { it.bezeichnung }))
                    .put("standardModus", Modus.AENDERUNGEN.bezeichnung)
                    .put("wartenderCode", wartenderCode ?: JSONObject.NULL))
                wartenderCode = null   // nur einmal ausliefern
            }

            pfad == "/api/plan" && verfahren == "GET" -> {
                val laufend = konto
                    ?: return sendeJson(strom, 409,
                        JSONObject().put("fehler", "Kein Konto eingerichtet."))
                val felder = abfrageFelder(abfrage)
                val montag = try {
                    tagAus(felder["montag"].orEmpty())
                } catch (_: Exception) {
                    return sendeJson(strom, 400, JSONObject().put("fehler", "Ungültiges Datum."))
                }
                val modus = Modus.entries.firstOrNull { it.bezeichnung == felder["modus"] }
                    ?: Modus.AENDERUNGEN
                try {
                    val termine = laufend.termine(montag, modus)
                    sendeJson(strom, 200, JSONObject()
                        .put("name", laufend.anzeigename)
                        .put("montag", felder["montag"])
                        .put("modus", modus.bezeichnung)
                        .put("termine", JSONArray(termine.map { it.alsJson() })))
                } catch (fehler: UntisFehler) {
                    sendeJson(strom, 502, JSONObject().put("fehler", fehler.message))
                }
            }

            pfad == "/api/hausaufgaben" && verfahren == "GET" -> {
                val laufend = konto
                    ?: return sendeJson(strom, 409,
                        JSONObject().put("fehler", "Kein Konto eingerichtet."))
                val felder = abfrageFelder(abfrage)
                val montag = try {
                    tagAus(felder["montag"].orEmpty())
                } catch (_: Exception) {
                    return sendeJson(strom, 400, JSONObject().put("fehler", "Ungültiges Datum."))
                }
                try {
                    val aufgaben = laufend.hausaufgaben(montag)
                    sendeJson(strom, 200, JSONObject()
                        .put("name", laufend.anzeigename)
                        .put("montag", felder["montag"])
                        .put("aufgaben", JSONArray(aufgaben.map { it.alsJson() })))
                } catch (fehler: UntisFehler) {
                    sendeJson(strom, 502, JSONObject().put("fehler", fehler.message))
                }
            }

            pfad == "/api/konto" && verfahren == "POST" -> {
                val daten = try { JSONObject(rumpf) } catch (_: Exception) { JSONObject() }
                val zugang = try {
                    val qr = daten.optString("qr")
                    if (qr.isNotBlank()) Zugang.ausQr(qr) else Zugang(
                        server = daten.optString("server").trim()
                            .removePrefix("https://").removePrefix("http://").trimEnd('/'),
                        schule = daten.optString("schule").trim(),
                        benutzer = daten.optString("benutzer").trim(),
                        schluessel = daten.optString("schluessel").replace(" ", "").trim().uppercase(),
                    )
                } catch (fehler: UntisFehler) {
                    return sendeJson(strom, 400, JSONObject().put("fehler", fehler.message))
                }

                if (!zugang.vollstaendig) {
                    return sendeJson(strom, 400, JSONObject().put("fehler", "Es fehlen noch Angaben."))
                }
                try {
                    val neu = UntisKonto(zugang)
                    val name = neu.anmelden()
                    konto = neu
                    if (daten.optBoolean("merken", true)) Konto.speichern(zusammenhang, zugang)
                    sendeJson(strom, 200, JSONObject()
                        .put("ok", true).put("name", name).put("benutzer", zugang.benutzer))
                } catch (fehler: UntisFehler) {
                    sendeJson(strom, 502, JSONObject().put("fehler", fehler.message))
                }
            }

            pfad == "/api/konto" && verfahren == "DELETE" -> {
                Konto.loeschen(zusammenhang)
                konto = null
                sendeJson(strom, 200, JSONObject().put("ok", true))
            }

            else -> sendeJson(strom, 404, JSONObject().put("fehler", "Unbekannter Aufruf."))
        }
    }

    private fun abfrageFelder(abfrage: String): Map<String, String> =
        abfrage.split('&').mapNotNull { teil ->
            val trenn = teil.indexOf('=')
            if (trenn <= 0) null
            else teil.substring(0, trenn) to
                java.net.URLDecoder.decode(teil.substring(trenn + 1), "UTF-8")
        }.toMap()

    private fun tagAus(iso: String): Calendar {
        val formatierer = SimpleDateFormat("yyyy-MM-dd", Locale.GERMANY)
        formatierer.isLenient = false
        return Calendar.getInstance().apply {
            time = formatierer.parse(iso)!!
            set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
        }
    }
}
