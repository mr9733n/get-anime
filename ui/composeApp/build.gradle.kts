import org.jetbrains.compose.desktop.application.dsl.TargetFormat
import org.jetbrains.kotlin.gradle.ExperimentalKotlinGradlePluginApi
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidApplication)
    alias(libs.plugins.composeMultiplatform)
    alias(libs.plugins.composeCompiler)
    alias(libs.plugins.kotlinSerialization)
}

kotlin {
    androidTarget {
        @OptIn(ExperimentalKotlinGradlePluginApi::class)
        compilerOptions {
            jvmTarget.set(JvmTarget.JVM_11)
        }
    }

    // Kotlin 2.0 / CMP 1.7: mainRun sets mainClass on the KotlinJvmRun task
    @OptIn(ExperimentalKotlinGradlePluginApi::class)
    jvm("desktop") {
        mainRun {
            mainClass.set("app.anime.MainKt")
        }
    }

    sourceSets {
        val desktopMain by getting

        androidMain.dependencies {
            implementation(compose.preview)
            implementation(libs.androidx.activity.compose)
            // TV-specific Compose
            implementation(libs.androidx.tv.foundation)
            implementation(libs.androidx.tv.material)
            // Ktor engine for Android (OkHttp)
            implementation(libs.ktor.client.okhttp)
        }

        commonMain.dependencies {
            implementation(compose.runtime)
            implementation(compose.foundation)
            implementation(compose.material3)
            implementation(compose.materialIconsExtended)
            implementation(compose.ui)
            implementation(compose.components.resources)
            implementation(compose.components.uiToolingPreview)

            // KMP ViewModel
            implementation(libs.lifecycle.viewmodel)
            implementation(libs.lifecycle.viewmodel.compose)

            // Navigation
            implementation(libs.navigation.compose)

            // Coroutines, serialization, datetime
            implementation(libs.kotlinx.coroutines.core)
            implementation(libs.kotlinx.serialization.json)
            implementation(libs.kotlinx.datetime)

            // Ktor core + content negotiation (engine injected per-platform)
            implementation(libs.ktor.client.core)
            implementation(libs.ktor.client.content.neg)
            implementation(libs.ktor.serialization.json)

            // Image loading — Coil3 KMP (uses the Ktor engine already on classpath)
            implementation(libs.coil3.compose)
            implementation(libs.coil3.network.ktor)
        }

        desktopMain.dependencies {
            implementation(compose.desktop.currentOs)
            implementation(libs.kotlinx.coroutines.swing)
            // Ktor engine for Desktop (JVM CIO — pure Kotlin, no native deps)
            implementation(libs.ktor.client.cio)
        }
    }
}

android {
    namespace = "app.anime"
    compileSdk = libs.versions.agp.get().let { 35 }

    sourceSets["main"].manifest.srcFile("src/androidMain/AndroidManifest.xml")
    sourceSets["main"].res.srcDirs("src/androidMain/res")
    sourceSets["main"].resources.srcDirs("src/commonMain/resources")

    defaultConfig {
        applicationId = "app.anime.player"
        minSdk = 21
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

// compose.desktop is kept for native distribution packaging (Dmg/Msi/Deb).
// mainClass for desktopRun is set via mainRun {} above (KotlinJvmRun, Kotlin 2.0 API).
compose.desktop {
    application {
        mainClass = "app.anime.MainKt"
        nativeDistributions {
            targetFormats(TargetFormat.Dmg, TargetFormat.Msi, TargetFormat.Deb)
            packageName = "AnimePlayer"
            packageVersion = "1.0.0"
        }
    }
}
