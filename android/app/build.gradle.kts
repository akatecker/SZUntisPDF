plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "io.github.akatecker.szuntispdf"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.akatecker.szuntispdf"
        minSdk = 24            // Android 7, deckt praktisch alle Geraete ab
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
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
