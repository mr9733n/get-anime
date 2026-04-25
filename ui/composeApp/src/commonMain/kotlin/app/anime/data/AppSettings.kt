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

    /** Whether to use system mpv/vlc for desktop playback. */
    var playerCommand: String

    companion object {
        const val DEFAULT_BACKEND_URL = "http://localhost:8765"
        const val DEFAULT_PLAYER_COMMAND = "mpv"
    }
}

/** Create the platform-specific AppSettings implementation. */
expect fun createAppSettings(): AppSettings
