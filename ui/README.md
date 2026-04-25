# Anime Player UI — Build & Deploy Guide

Kotlin Multiplatform + Compose Multiplatform 1.7.1  
Targets: **Desktop (Windows / Linux / macOS)** and **Android TV**

---

## Prerequisites

| Tool | Version |
|------|---------|
| JDK | 17+ (21 recommended) |
| Android Studio | Hedgehog+ (or IntelliJ IDEA with KMP plugin) |
| Gradle | 8.9 (wrapper included — use `./gradlew` / `gradlew.bat`) |
| Android SDK | API 35, min API 21 |

---

## Quick Start — Desktop

```bash
cd ui
# Run Desktop app (connects to backend at http://localhost:8765 by default)
./gradlew :composeApp:desktopRun

# Windows:
gradlew.bat :composeApp:desktopRun
```

The app reads/saves the backend URL in a settings file (`~/.anime_player/settings.properties`).  
Change the URL in-app via **Settings → Backend сервер**.

---

## Build Desktop Distributable

```bash
# Windows installer (MSI)
./gradlew :composeApp:packageMsi

# Linux DEB
./gradlew :composeApp:packageDeb

# macOS DMG
./gradlew :composeApp:packageDmg

# Output: ui/composeApp/build/compose/binaries/main/
```

---

## Build Android TV APK

```bash
cd ui

# Debug APK (install on TV via adb)
./gradlew :composeApp:assembleDebug

# Release APK (needs keystore — see below)
./gradlew :composeApp:assembleRelease

# Output: ui/composeApp/build/outputs/apk/
```

### Install on Android TV via ADB

```bash
# Find TV IP: Settings → Network → Advanced → IP address
adb connect <TV_IP>:5555
adb install composeApp/build/outputs/apk/debug/composeApp-debug.apk
```

### Release Keystore (one-time setup)

```bash
keytool -genkey -v -keystore anime_player.keystore \
  -alias anime_player -keyalg RSA -keysize 2048 -validity 10000
```

Add to `ui/local.properties`:
```properties
KEYSTORE_PATH=/path/to/anime_player.keystore
KEYSTORE_PASSWORD=your_pass
KEY_ALIAS=anime_player
KEY_PASSWORD=your_pass
```

---

## Backend Connection

The UI connects to the Python HTTP backend.  
Default: `http://localhost:8765` (Desktop) or `http://<LAN-IP>:8765` (Android TV).

To change: open Settings screen → **Backend сервер** → enter URL → **Сохранить** → **Проверить соединение**.

---

## Project Layout

```
ui/
├── composeApp/
│   ├── src/
│   │   ├── commonMain/     ← shared Kotlin code (ViewModels, Repository, DTOs, most screens)
│   │   ├── desktopMain/    ← Desktop-specific: main.kt, player launch, AppSettings
│   │   └── androidMain/    ← Android-specific: MainActivity, TV screens, AppSettings
│   └── build.gradle.kts
├── gradle/
│   └── libs.versions.toml  ← dependency catalog
└── README.md               ← this file
```

---

## Key Dependencies

| Library | Purpose |
|---------|---------|
| Compose Multiplatform 1.7.1 | UI framework |
| Ktor 3.0.1 | HTTP client (backend API calls) |
| Coil3 3.1.0 | Async image loading (poster images) |
| Navigation Compose | Screen routing |
| Lifecycle ViewModel KMP | State management |
| kotlinx.serialization | JSON deserialization |
| kotlinx.datetime | Date/time utilities |
