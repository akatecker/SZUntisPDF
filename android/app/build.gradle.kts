plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

/**
 * Versionsnummer aus dem Git-Tag, sonst aus SZUNTIS_VERSION.
 *
 * Fest eingetragen wurde sie schon einmal vergessen: Das 1.3.0-Release trug
 * im macOS-Bündel noch 1.2.0.
 */
val fassung: String = (System.getenv("SZUNTIS_VERSION")?.removePrefix("v")?.takeIf { it.isNotBlank() }
    ?: runCatching {
        val vorgang = ProcessBuilder("git", "describe", "--tags", "--abbrev=0")
            .directory(rootDir).redirectErrorStream(true).start()
        vorgang.inputStream.bufferedReader().readText().trim().removePrefix("v")
    }.getOrDefault(""))
    .split(".").filter { it.toIntOrNull() != null }.joinToString(".")
    .ifBlank { "0.0.0" }

/** Aus 1.3.0 wird 10300 - monoton steigend, wie Android es verlangt. */
val fassungsNummer: Int = fassung.split(".").map { it.toIntOrNull() ?: 0 }
    .let { (it + listOf(0, 0, 0)).take(3) }
    .let { (gross, mittel, klein) -> gross * 10000 + mittel * 100 + klein }
    .coerceAtLeast(1)

android {
    namespace = "io.github.akatecker.szuntispdf"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.akatecker.szuntispdf"
        minSdk = 24            // Android 7, deckt praktisch alle Geraete ab
        targetSdk = 35
        versionCode = fassungsNummer
        versionName = fassung
    }

    // Liegt ein eigener Schluessel bereit, wird damit signiert - nur so behalten
    // aufeinanderfolgende Veroeffentlichungen dieselbe Signatur und lassen sich
    // ueber eine bestehende Installation druebersetzen. Sonst Debug-Signatur,
    // damit sich die APK wenigstens neu installieren laesst.
    val eigenerSchluessel = rootProject.file("schluessel.jks")
    signingConfigs {
        if (eigenerSchluessel.exists()) {
            create("veroeffentlichung") {
                storeFile = eigenerSchluessel
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORT")
                keyAlias = System.getenv("ANDROID_SCHLUESSEL_ALIAS") ?: "szuntispdf"
                keyPassword = System.getenv("ANDROID_KEYSTORE_PASSWORT")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = if (eigenerSchluessel.exists()) {
                signingConfigs.getByName("veroeffentlichung")
            } else {
                signingConfigs.getByName("debug")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    packaging {
        resources.excludes += setOf("META-INF/*.version", "kotlin/**", "DebugProbesKt.bin")
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
}
