package app.anime.data

/**
 * Persistent app settings.
 * Key stored preference: backend server URL.
 *
 * Desktop  → ~/.config/anime-player/settings.json
 * Android  → SharedPreferences
 */
interface AppSettings {
    /** Backend base URL, e.g. "http://192.168.1.100:8765" */
    var backendUrl: String

    /** Command used to launch a video player for media streams (Desktop only). */
    var playerCommand: String

    /**
     * Command / path used to open web-player page URLs in a browser (Desktop only).
     * Empty string = use OS default browser.
     */
    var browserCommand: String

    companion object {
        const val DEFAULT_BACKEND_URL = "http://localhost:8765"
        const val DEFAULT_PLAYER_COMMAND = "mpv"
        const val DEFAULT_BROWSER_COMMAND = ""
    }
}

/** Create the platform-specific AppSettings implementation. */
expect fun createAppSettings(): AppSettings
