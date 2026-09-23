package io.github.akatecker.szuntispdf

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.ByteBuffer
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** Fehler der Gegenstelle oder der Anmeldung. */
class UntisFehler(meldung: String) : Exception(meldung)

/** Die vier Werte aus dem `untis://setschool`-QR-Code. */
data class Zugang(
    val server: String,
    val schule: String,
    val benutzer: String,
    val schluessel: String,
) {
    val vollstaendig: Boolean
        get() = server.isNotBlank() && schule.isNotBlank() &&
            benutzer.isNotBlank() && schluessel.isNotBlank()

    companion object {
        /** Liest einen `untis://setschool?...`-String ein. */
        fun ausQr(qr: String): Zugang {
            val felder = qr.substringAfter('?', "").split('&')
                .mapNotNull { teil ->
                    val trenn = teil.indexOf('=')
                    if (trenn <= 0) null
                    else teil.substring(0, trenn) to
                        java.net.URLDecoder.decode(teil.substring(trenn + 1), "UTF-8")
                }.toMap()

            val fehlend = listOf("url", "school", "user", "key").filter { felder[it].isNullOrBlank() }
            if (fehlend.isNotEmpty()) {
                throw UntisFehler("QR-Code unvollständig, es fehlt: ${fehlend.joinToString(", ")}")
            }
            return Zugang(
                server = felder.getValue("url").removePrefix("https://").removePrefix("http://").trimEnd('/'),
                schule = felder.getValue("school"),
                benutzer = felder.getValue("user"),
                schluessel = felder.getValue("key"),
            )
        }
    }
}

/** Woher ein Termin stammt. */
enum class Quelle { EIGEN, KLASSE }

/** Wie stark der Klassenplan einbezogen wird. */
enum class Modus(val bezeichnung: String) {
    NUR_EIGEN("Nur mein Plan"),
    AENDERUNGEN("Mein Plan + Klassenänderungen"),
    KLASSE_VOLL("Klassenplan vollständig"),
}

/** Ein Eintrag im Stundenplan, bereits in Klartext aufgelöst. */
data class Termin(
    val beginn: String,          // "2026-09-14T08:15"
    var ende: String,
    val kuerzel: String,
    val fach: String,
    val fachExakt: Boolean,
    val lehrkraft: String,
    val raum: String,
    val klasse: String,
    var status: String,
    val info: String,
    var entfaellt: Boolean,
    val quelle: Quelle,
    var klassenHinweis: String = "",
) {
    val tag: String get() = beginn.substring(0, 10)
    val ausKlassenplan: Boolean get() = quelle == Quelle.KLASSE

    fun alsJson(): JSONObject = JSONObject()
        .put("beginn", beginn).put("ende", ende).put("tag", tag)
        .put("kuerzel", kuerzel).put("fach", fach).put("fachExakt", fachExakt)
        .put("lehrkraft", lehrkraft).put("raum", raum).put("klasse", klasse)
        .put("status", status).put("info", info).put("entfaellt", entfaellt)
        .put("ausKlassenplan", ausKlassenplan).put("klassenHinweis", klassenHinweis)
}

/** Eine Hausübung, bereits mit Fach und Lehrkraft aufgelöst. */
data class Hausaufgabe(
    val aufgegeben: String,     // "2026-09-23"
    val faellig: String,
    val kuerzel: String,
    val fach: String,
    val fachExakt: Boolean,
    val lehrkraft: String,
    val text: String,
    val anmerkung: String,
    val erledigt: Boolean,
    val anhaenge: Int,
) {
    val laeuftLaenger: Boolean get() = faellig > aufgegeben

    fun alsJson(): JSONObject = JSONObject()
        .put("aufgegeben", aufgegeben).put("faellig", faellig)
        .put("kuerzel", kuerzel).put("fach", fach).put("fachExakt", fachExakt)
        .put("lehrkraft", lehrkraft).put("text", text).put("anmerkung", anmerkung)
        .put("erledigt", erledigt).put("anhaenge", anhaenge)
        .put("laeuftLaenger", laeuftLaenger)
}

/**
 * Angemeldete Sitzung für genau ein WebUntis-Konto.
 *
 * Nutzt dieselbe JSON-RPC-Schnittstelle wie die Untis-Mobile-App: Aus dem
 * Base32-Schlüssel des QR-Codes wird pro Aufruf ein TOTP-Einmalcode berechnet.
 * Anders als im Browser gibt es hier keine CORS-Beschränkung - eine native App
 * hat keinen Origin.
 */
class UntisKonto(val zugang: Zugang) {

    private var stammdaten: JSONObject? = null
    private var benutzerdaten: JSONObject? = null
    private var stammklasseId: Int? = null
    var anzeigename: String = ""
        private set

    // -- TOTP --------------------------------------------------------------

    private fun einmalcode(): Int {
        val roh = zugang.schluessel.uppercase().replace(" ", "")
        val schluessel = base32(roh)
        val zaehler = System.currentTimeMillis() / 1000 / 30
        val mac = Mac.getInstance("HmacSHA1")
        mac.init(SecretKeySpec(schluessel, "HmacSHA1"))
        val abdruck = mac.doFinal(ByteBuffer.allocate(8).putLong(zaehler).array())
        val versatz = abdruck[abdruck.size - 1].toInt() and 0x0F
        val wert = ((abdruck[versatz].toInt() and 0x7F) shl 24) or
            ((abdruck[versatz + 1].toInt() and 0xFF) shl 16) or
            ((abdruck[versatz + 2].toInt() and 0xFF) shl 8) or
            (abdruck[versatz + 3].toInt() and 0xFF)
        return wert % 1_000_000
    }

    /** Android bringt kein Base32 mit - RFC 4648 ist aber schnell gemacht. */
    private fun base32(text: String): ByteArray {
        val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        var puffer = 0
        var bits = 0
        val ergebnis = ArrayList<Byte>(text.length)
        for (zeichen in text) {
            if (zeichen == '=') continue
            val wert = alphabet.indexOf(zeichen)
            if (wert < 0) throw UntisFehler("Der Schlüssel enthält ein ungültiges Zeichen: $zeichen")
            puffer = (puffer shl 5) or wert
            bits += 5
            if (bits >= 8) {
                bits -= 8
                ergebnis.add(((puffer shr bits) and 0xFF).toByte())
            }
        }
        return ergebnis.toByteArray()
    }

    private fun auth(): JSONObject = JSONObject()
        .put("clientTime", System.currentTimeMillis())
        .put("user", zugang.benutzer)
        .put("otp", einmalcode())

    // -- Transport ---------------------------------------------------------

    private fun rpc(methode: String, parameter: JSONObject): JSONObject {
        val abfrage = "m=${enk(methode)}&school=${enk(zugang.schule)}&v=i2.2"
        val adresse = URL("https://${zugang.server}/WebUntis/jsonrpc_intern.do?$abfrage")
        val rumpf = JSONObject()
            .put("id", "szu").put("method", methode)
            .put("params", JSONArray().put(parameter))
            .put("jsonrpc", "2.0")
            .toString().toByteArray(Charsets.UTF_8)

        val verbindung = (adresse.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 20_000
            readTimeout = 25_000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("User-Agent", "SZUntisPDF-Android/1.0")
        }

        val antwort = try {
            verbindung.outputStream.use { it.write(rumpf) }
            val text = (if (verbindung.responseCode in 200..299) verbindung.inputStream
                        else verbindung.errorStream).bufferedReader().use { it.readText() }
            if (verbindung.responseCode !in 200..299 && text.isBlank()) {
                throw UntisFehler("${zugang.server} antwortete mit ${verbindung.responseCode}")
            }
            JSONObject(text)
        } catch (fehler: IOException) {
            throw UntisFehler("Keine Verbindung zu ${zugang.server}: ${fehler.message}")
        } catch (fehler: org.json.JSONException) {
            throw UntisFehler("Unerwartete Antwort - Server erreichbar?")
        } finally {
            verbindung.disconnect()
        }

        antwort.optJSONObject("error")?.let { problem ->
            val code = problem.optInt("code")
            val meldung = if (code == -8504 || code == -8998) {
                "Anmeldung abgelehnt. Schlüssel, Benutzername oder Schule prüfen " +
                    "- oder die Uhr des Geräts weicht zu stark ab."
            } else {
                problem.optString("message", "unbekannter Fehler")
            }
            throw UntisFehler(meldung)
        }
        return antwort.getJSONObject("result")
    }

    private fun enk(wert: String) = URLEncoder.encode(wert, "UTF-8")

    // -- Stammdaten --------------------------------------------------------

    fun anmelden(): String {
        val ergebnis = rpc("getUserData2017", JSONObject().put("auth", auth()))
        stammdaten = ergebnis.getJSONObject("masterData")
        benutzerdaten = ergebnis.getJSONObject("userData")
        anzeigename = benutzerdaten?.optString("displayName").orEmpty()
            .ifBlank { zugang.benutzer }
        return anzeigename
    }

    private fun register(name: String): Map<Int, JSONObject> {
        val feld = stammdaten?.optJSONArray(name) ?: return emptyMap()
        return (0 until feld.length()).associate { i ->
            val eintrag = feld.getJSONObject(i)
            eintrag.getInt("id") to eintrag
        }
    }

    // -- Stundenplan -------------------------------------------------------

    private fun perioden(typ: String, id: Int, von: Calendar, bis: Calendar): JSONArray {
        val ergebnis = rpc(
            "getTimetable2017",
            JSONObject()
                .put("id", id).put("type", typ)
                .put("startDate", alsZahl(von)).put("endDate", alsZahl(bis))
                .put("masterDataTimestamp", stammdaten?.optLong("timeStamp") ?: 0L)
                .put("timetableTimestamp", 0)
                .put("timetableTimestamps", JSONArray())
                .put("auth", auth()),
        )
        return ergebnis.optJSONObject("timetable")?.optJSONArray("periods") ?: JSONArray()
    }

    /**
     * Ermittelt die Stammklasse aus dem eigenen Stundenplan.
     *
     * `userData.klassenIds` ist bei Schülerkonten leer, und gekoppelte Stunden
     * nennen mehrere Klassen. Die über vier Wochen häufigste ist die richtige.
     */
    private fun stammklasse(montag: Calendar): Int? {
        stammklasseId?.let { return it }
        val zaehler = HashMap<Int, Int>()
        val elemId = benutzerdaten?.optInt("elemId") ?: return null
        val elemTyp = benutzerdaten?.optString("elemType").orEmpty().ifBlank { "STUDENT" }

        for (woche in 0 until 4) {
            val von = montag.clone() as Calendar
            von.add(Calendar.DAY_OF_MONTH, woche * 7)
            val bis = von.clone() as Calendar
            bis.add(Calendar.DAY_OF_MONTH, 6)
            val gefunden = perioden(elemTyp, elemId, von, bis)
            for (i in 0 until gefunden.length()) {
                val elemente = gefunden.getJSONObject(i).optJSONArray("elements") ?: continue
                for (k in 0 until elemente.length()) {
                    val element = elemente.getJSONObject(k)
                    if (element.optString("type") == "CLASS" && element.optInt("id") > 0) {
                        zaehler.merge(element.getInt("id"), 1, Int::plus)
                    }
                }
            }
        }
        stammklasseId = zaehler.maxByOrNull { it.value }?.key
        return stammklasseId
    }

    /**
     * Hausübungen, die die Woche ab [montag] berühren.
     *
     * WebUntis filtert eine Anfrage nach dem **Fälligkeitsdatum**. Eine am
     * Mittwoch aufgegebene Aufgabe, die erst nächsten Montag fällig ist, fiele
     * damit aus der Wochenansicht heraus, obwohl sie genau jetzt zu erledigen
     * ist. Deshalb wird großzügig abgefragt und danach auf Überschneidung
     * geprüft. ISO-Daten lassen sich dafür als Text vergleichen.
     */
    fun hausaufgaben(montag: Calendar): List<Hausaufgabe> {
        if (benutzerdaten == null) anmelden()
        val elemId = benutzerdaten?.optInt("elemId") ?: throw UntisFehler("Kein Konto angemeldet.")
        val elemTyp = benutzerdaten?.optString("elemType").orEmpty().ifBlank { "STUDENT" }

        val sonntag = (montag.clone() as Calendar).apply { add(Calendar.DAY_OF_MONTH, 6) }
        val frueh = (montag.clone() as Calendar).apply { add(Calendar.DAY_OF_MONTH, -30) }
        val spaet = (sonntag.clone() as Calendar).apply { add(Calendar.DAY_OF_MONTH, 90) }

        val ergebnis = rpc(
            "getHomeWork2017",
            JSONObject()
                .put("id", elemId).put("type", elemTyp)
                .put("startDate", alsZahl(frueh)).put("endDate", alsZahl(spaet))
                .put("auth", auth()),
        )

        val montagIso = alsIso(montag)
        val sonntagIso = alsIso(sonntag)
        val stunden = ergebnis.optJSONObject("lessonsById") ?: JSONObject()
        val faecher = register("subjects")
        val lehrkraefte = register("teachers")

        val gefunden = ArrayList<Hausaufgabe>()
        val liste = ergebnis.optJSONArray("homeWorks") ?: JSONArray()
        for (i in 0 until liste.length()) {
            val eintrag = liste.getJSONObject(i)
            val aufgegeben = eintrag.optString("startDate")
            val faellig = eintrag.optString("endDate")
            if (aufgegeben.isEmpty() || faellig.isEmpty()) continue
            if (aufgegeben > sonntagIso || faellig < montagIso) continue

            val stunde = stunden.optJSONObject(eintrag.optInt("lessonId").toString())
            val fachEintrag = faecher[stunde?.optInt("subjectId")]
            val kuerzel = fachEintrag?.optString("name").orEmpty()
            val (fach, exakt) = if (kuerzel.isNotEmpty()) {
                Faecher.klartext(kuerzel, fachEintrag?.optString("longName").orEmpty())
            } else {
                "ohne Gegenstand" to true
            }

            val namen = ArrayList<String>()
            stunde?.optJSONArray("teacherIds")?.let { kennungen ->
                for (k in 0 until kennungen.length()) {
                    val person = lehrkraefte[kennungen.getInt(k)]
                    val name = person?.optString("lastName").orEmpty()
                        .ifBlank { person?.optString("name").orEmpty() }
                    if (name.isNotBlank()) namen.add(name)
                }
            }

            gefunden.add(
                Hausaufgabe(
                    aufgegeben = aufgegeben,
                    faellig = faellig,
                    kuerzel = kuerzel,
                    fach = fach,
                    fachExakt = exakt,
                    lehrkraft = namen.distinct().sorted().joinToString(", "),
                    text = eintrag.optString("text").trim(),
                    anmerkung = eintrag.optString("remark").takeIf { it != "null" }.orEmpty().trim(),
                    erledigt = eintrag.optBoolean("completed"),
                    anhaenge = eintrag.optJSONArray("attachments")?.length() ?: 0,
                )
            )
        }
        return gefunden.sortedWith(compareBy({ it.faellig }, { it.kuerzel }, { it.text }))
    }

    private fun alsIso(tag: Calendar): String {
        val formatierer = SimpleDateFormat("yyyy-MM-dd", Locale.GERMANY)
        formatierer.timeZone = tag.timeZone
        return formatierer.format(tag.time)
    }

    fun termine(montag: Calendar, modus: Modus): List<Termin> {
        if (benutzerdaten == null) anmelden()
        val elemId = benutzerdaten?.optInt("elemId") ?: throw UntisFehler("Kein Konto angemeldet.")
        val elemTyp = benutzerdaten?.optString("elemType").orEmpty().ifBlank { "STUDENT" }
        val sonntag = (montag.clone() as Calendar).apply { add(Calendar.DAY_OF_MONTH, 6) }

        val eigen = umwandeln(perioden(elemTyp, elemId, montag, sonntag), Quelle.EIGEN)
        var klasse = emptyList<Pair<Int, Termin>>()
        if (modus != Modus.NUR_EIGEN) {
            stammklasse(montag)?.let { klassenId ->
                klasse = try {
                    umwandeln(perioden("CLASS", klassenId, montag, sonntag), Quelle.KLASSE)
                } catch (_: UntisFehler) {
                    emptyList()   // lieber den eigenen Plan zeigen als gar nichts
                }
            }
        }
        return zusammenfuehren(eigen, klasse, modus)
    }

    // -- Umwandlung --------------------------------------------------------

    private fun umwandeln(perioden: JSONArray, quelle: Quelle): List<Pair<Int, Termin>> {
        val faecher = register("subjects")
        val lehrkraefte = register("teachers")
        val raeume = register("rooms")
        val klassen = register("klassen")
        val ergebnis = ArrayList<Pair<Int, Termin>>(perioden.length())

        for (i in 0 until perioden.length()) {
            val periode = perioden.getJSONObject(i)
            val nachTyp = HashMap<String, MutableList<JSONObject>>()
            periode.optJSONArray("elements")?.let { elemente ->
                for (k in 0 until elemente.length()) {
                    val element = elemente.getJSONObject(k)
                    nachTyp.getOrPut(element.optString("type")) { ArrayList() }.add(element)
                }
            }

            fun namen(typ: String, quelle2: Map<Int, JSONObject>, feld: String = "name"): String =
                nachTyp[typ].orEmpty()
                    .mapNotNull { quelle2[it.optInt("id")]?.optString(feld) }
                    .filter { it.isNotBlank() }
                    .distinct().sorted().joinToString(", ")

            val zustaende = ArrayList<String>()
            periode.optJSONArray("is")?.let { for (k in 0 until it.length()) zustaende.add(it.getString(k)) }

            val text = periode.optJSONObject("text")
            val hinweis = listOf("substitution", "info", "lesson")
                .mapNotNull { text?.optString(it)?.trim() }
                .filter { it.isNotEmpty() }
                .distinct().joinToString(" · ")

            val fachEintrag = nachTyp["SUBJECT"]?.firstNotNullOfOrNull { faecher[it.optInt("id")] }
            val kuerzel = fachEintrag?.optString("name").orEmpty()
            val (fach, exakt) = if (kuerzel.isNotEmpty()) {
                Faecher.klartext(kuerzel, fachEintrag?.optString("longName").orEmpty())
            } else {
                // Stunden ohne Gegenstand (Klassenvorstand, Fototermin ...)
                val ersatz = text?.optString("lesson").orEmpty().ifBlank { hinweis }
                    .ifBlank { "ohne Gegenstand" }
                ersatz to true
            }

            ergebnis.add(
                periode.optInt("lessonId") to Termin(
                    beginn = periode.getString("startDateTime").removeSuffix("Z"),
                    ende = periode.getString("endDateTime").removeSuffix("Z"),
                    kuerzel = kuerzel,
                    fach = fach,
                    fachExakt = exakt,
                    lehrkraft = namen("TEACHER", lehrkraefte, "lastName")
                        .ifBlank { namen("TEACHER", lehrkraefte) },
                    raum = namen("ROOM", raeume),
                    klasse = namen("CLASS", klassen),
                    status = status(zustaende),
                    info = hinweis,
                    entfaellt = zustaende.contains("CANCELLED"),
                    quelle = quelle,
                )
            )
        }
        return ergebnis
    }

    private fun status(zustaende: List<String>): String {
        val tabelle = mapOf(
            "CANCELLED" to "Entfällt", "SUBSTITUTION" to "Vertretung",
            "IRREGULAR" to "Geändert", "ADDITIONAL" to "Zusatzstunde",
            "SHIFT" to "Verlegt", "ROOMSUBSTITUTION" to "Raumänderung",
            "EXAM" to "Prüfung", "EVENT" to "Termin",
            "STANDBY" to "Bereitschaft", "OFFICEHOUR" to "Sprechstunde",
        )
        return zustaende.mapNotNull { tabelle[it] }.joinToString(", ")
    }

    private fun alsZahl(tag: Calendar): Int {
        val formatierer = SimpleDateFormat("yyyyMMdd", Locale.GERMANY)
        formatierer.timeZone = tag.timeZone
        return formatierer.format(tag.time).toInt()
    }

    companion object {
        /** Zustände, die eine Planänderung anzeigen. */
        private val AENDERUNGEN = setOf(
            "Entfällt", "Vertretung", "Geändert", "Zusatzstunde",
            "Verlegt", "Raumänderung", "Prüfung", "Termin",
        )

        /**
         * Führt persönlichen Plan und Klassenplan zusammen.
         *
         * Vorrang hat immer der persönliche Plan. Der Klassenplan ist eine
         * Obermenge und enthält auch Parallelgruppen, die dieses Kind gar nicht
         * besucht - deshalb wird er gefiltert statt blind angehängt.
         */
        fun zusammenfuehren(
            eigen: List<Pair<Int, Termin>>,
            klasse: List<Pair<Int, Termin>>,
            modus: Modus,
        ): List<Termin> {
            val eigenIndex = eigen.associateBy { (stunde, t) -> Triple(stunde, t.beginn, t.ende) }
            val eigeneFaecher = eigen.map { it.second.kuerzel }.filter { it.isNotEmpty() }.toSet()
            val zusatz = ArrayList<Pair<Int, Termin>>()

            for ((stunde, termin) in klasse) {
                val vorhanden = eigenIndex[Triple(stunde, termin.beginn, termin.ende)]?.second
                if (vorhanden != null) {
                    if (termin.status != vorhanden.status) {
                        vorhanden.klassenHinweis =
                            "Klassenplan meldet: ${termin.status.ifBlank { "regulär" }}"
                        if (termin.status.isNotBlank()) vorhanden.status = termin.status
                        vorhanden.entfaellt = termin.entfaellt
                    }
                    continue
                }

                // Dasselbe Fach zur selben Zeit im eigenen Plan? Dann ist es
                // die Parallelgruppe derselben Stunde und gehoert nicht dazu.
                val schonBelegt = eigen.any { (_, anderer) ->
                    anderer.kuerzel == termin.kuerzel &&
                        anderer.beginn < termin.ende && termin.beginn < anderer.ende
                }
                if (schonBelegt) continue

                when (modus) {
                    Modus.KLASSE_VOLL -> zusatz.add(stunde to termin)
                    Modus.AENDERUNGEN -> {
                        val meldetAenderung = termin.status.split(",")
                            .any { it.trim() in AENDERUNGEN }
                        if (meldetAenderung && termin.kuerzel in eigeneFaecher) {
                            zusatz.add(stunde to termin)
                        }
                    }
                    Modus.NUR_EIGEN -> Unit
                }
            }
            return zusammenfassen(eigen + zusatz)
        }

        /**
         * Fasst direkt aufeinanderfolgende Einheiten derselben Stunde zusammen.
         * WebUntis liefert Doppelstunden als zwei Einträge.
         */
        private fun zusammenfassen(roh: List<Pair<Int, Termin>>): List<Termin> {
            val sortiert = roh.sortedWith(compareBy({ it.second.beginn }, { it.second.kuerzel }))
            val ergebnis = ArrayList<Termin>()
            // Schluessel enthaelt die Quelle, damit ein Klasseneintrag nie mit
            // einem eigenen verschmilzt.
            val letzte = HashMap<Pair<Int, Quelle>, Termin>()

            for ((stunde, termin) in sortiert) {
                val gruppe = stunde to termin.quelle
                val vorheriger = letzte[gruppe]
                val passt = vorheriger != null && stunde != 0 &&
                    vorheriger.ende == termin.beginn &&
                    vorheriger.raum == termin.raum &&
                    vorheriger.status == termin.status
                if (passt) {
                    vorheriger!!.ende = termin.ende
                    continue
                }
                ergebnis.add(termin)
                letzte[gruppe] = termin
            }
            return ergebnis.sortedWith(compareBy({ it.beginn }, { it.kuerzel }))
        }

        /** Montag der Woche, in der `tag` liegt. */
        fun montagVon(tag: Date): Calendar = Calendar.getInstance(TimeZone.getDefault()).apply {
            time = tag
            set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
            val versatz = (get(Calendar.DAY_OF_WEEK) + 5) % 7   // Montag = 0
            add(Calendar.DAY_OF_MONTH, -versatz)
        }
    }
}
