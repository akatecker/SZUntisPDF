package io.github.akatecker.szuntispdf

import android.Manifest
import android.annotation.SuppressLint
import android.content.pm.PackageManager
import android.content.Intent
import android.os.Bundle
import android.widget.FrameLayout
import android.print.PrintAttributes
import android.print.PrintManager
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.addCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/**
 * Trägt die Oberfläche und verbindet sie mit den Dingen, die nur nativ gehen:
 * Kamera, Drucken und das Speichern als PDF.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var server: LokalerServer
    private lateinit var browser: WebView
    private var wartendeKameraAnfrage: PermissionRequest? = null

    private val kameraFrage = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { erlaubt ->
        val anfrage = wartendeKameraAnfrage
        wartendeKameraAnfrage = null
        if (erlaubt && anfrage != null) {
            anfrage.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))
        } else {
            anfrage?.deny()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(zustand: Bundle?) {
        super.onCreate(zustand)

        server = LokalerServer(this)
        server.starten()

        browser = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            // Die Oberflaeche kommt vom eigenen Server, nicht aus dem Netz.
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.mediaPlaybackRequiresUserGesture = false   // Kamerabild ohne Extra-Tipp
            webViewClient = WebViewClient()
            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(anfrage: PermissionRequest) {
                    if (!anfrage.resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)) {
                        return anfrage.deny()
                    }
                    val schon = ContextCompat.checkSelfPermission(
                        this@MainActivity, Manifest.permission.CAMERA
                    ) == PackageManager.PERMISSION_GRANTED
                    if (schon) {
                        anfrage.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))
                    } else {
                        // Erst das System fragen, dann der WebView antworten.
                        wartendeKameraAnfrage = anfrage
                        kameraFrage.launch(Manifest.permission.CAMERA)
                    }
                }
            }
            addJavascriptInterface(Bruecke(), "Android")
        }
        // Ab Android 15 zeichnen Apps standardmaessig unter Status- und
        // Navigationsleiste. Der Rahmen haelt die Oberflaeche davon frei.
        val rahmen = FrameLayout(this).apply { fitsSystemWindows = true }
        rahmen.addView(browser)
        setContentView(rahmen)
        ViewCompat.setOnApplyWindowInsetsListener(rahmen) { sicht, fenster ->
            val leisten = fenster.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
            )
            sicht.setPadding(leisten.left, leisten.top, leisten.right, leisten.bottom)
            WindowInsetsCompat.CONSUMED
        }

        codeAusIntent(intent)

        Thread {
            server.ausAblageLaden()
            runOnUiThread { browser.loadUrl(server.adresse) }
        }.start()

        onBackPressedDispatcher.addCallback(this) {
            if (browser.canGoBack()) browser.goBack() else finish()
        }
    }

    override fun onNewIntent(neu: Intent) {
        super.onNewIntent(neu)
        if (codeAusIntent(neu)) browser.reload()
    }

    /** Nimmt einen `untis://setschool?...`-Aufruf entgegen. */
    private fun codeAusIntent(auftrag: Intent?): Boolean {
        val adresse = auftrag?.data ?: return false
        if (adresse.scheme != "untis") return false
        server.wartenderCode = adresse.toString()
        return true
    }

    override fun onDestroy() {
        server.beenden()
        browser.destroy()
        super.onDestroy()
    }

    /**
     * Was die Oberfläche vom Gerät braucht.
     *
     * Die Methoden werden aus JavaScript aufgerufen und laufen deshalb nicht im
     * Oberflächen-Thread; alles, was die WebView anfasst, muss zurückgereicht
     * werden.
     */
    private inner class Bruecke {

        /**
         * Öffnet den Druckdialog von Android - dort auch "Als PDF speichern".
         *
         * Das Wochenraster braucht Querformat, die Aufgabenliste Hochformat.
         */
        @JavascriptInterface
        fun drucken(titel: String, quer: Boolean) {
            runOnUiThread {
                val dienst = getSystemService(PRINT_SERVICE) as PrintManager
                val name = titel.ifBlank { "Stundenplan" }
                val format = PrintAttributes.MediaSize.ISO_A4.let {
                    if (quer) it.asLandscape() else it.asPortrait()
                }
                dienst.print(
                    name,
                    browser.createPrintDocumentAdapter(name),
                    PrintAttributes.Builder()
                        .setMediaSize(format)
                        .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
                        .build(),
                )
            }
        }

        /** Sagt der Oberfläche, dass sie auf einem Telefon läuft. */
        @JavascriptInterface
        fun istAndroid(): Boolean = true
    }
}
