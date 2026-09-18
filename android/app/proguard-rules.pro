# Die Klasse, die dem WebView als JavaScript-Bruecke dient, darf nicht
# umbenannt werden - sonst findet die Oberflaeche sie nicht mehr.
-keepclassmembers class io.github.akatecker.szuntispdf.** {
    @android.webkit.JavascriptInterface <methods>;
}
