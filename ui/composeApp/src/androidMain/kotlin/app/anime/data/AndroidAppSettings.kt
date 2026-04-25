package app.anime.data

import android.content.Context
import android.content.SharedPreferences

/**
 * Android implementation — backed by SharedPreferences.
 * Context must be set before use (call AndroidAppSettings.init(context) in Application.onCreate).
 */
class AndroidAppSettings(private val prefs: SharedPreferences) : AppSettings {

    override var backendUrl: String
        get() = prefs.getString(KEY_BACKEND_URL, AppSettings.DEFAULT_BACKEND_URL)!!
        set(value) { prefs.edit().putString(KEY_BACKEND_URL, value).apply() }

    override var playerCommand: String
        get() = prefs.getString(KEY_PLAYER_CMD, AppSettings.DEFAULT_PLAYER_COMMAND)!!
        set(value) { prefs.edit().putString(KEY_PLAYER_CMD, value).apply() }

    companion object {
        private const val PREFS_NAME = "anime_player"
        private const val KEY_BACKEND_URL = "backend_url"
        private const val KEY_PLAYER_CMD = "player_command"

        // Held in a companion so we can call createAppSettings() without a Context param
        // (set in Application.onCreate or MainActivity.onCreate before any ViewModel is created)
        private lateinit var instance: AndroidAppSettings

        fun init(context: Context) {
            if (!::instance.isInitialized) {
                val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                instance = AndroidAppSettings(prefs)
            }
        }

        fun get(): AndroidAppSettings = instance
    }
}

actual fun createAppSettings(): AppSettings = AndroidAppSettings.get()
