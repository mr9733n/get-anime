package app.anime.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

@Serializable
private data class SettingsData(
    val backendUrl: String = AppSettings.DEFAULT_BACKEND_URL,
    val playerCommand: String = AppSettings.DEFAULT_PLAYER_COMMAND,
    val browserCommand: String = AppSettings.DEFAULT_BROWSER_COMMAND,
)

class DesktopAppSettings : AppSettings {

    private val file: File = File(
        System.getProperty("user.home"), ".config/anime-player/settings.json"
    ).also { it.parentFile.mkdirs() }

    private val json = Json { prettyPrint = true; ignoreUnknownKeys = true }
    private var data: SettingsData = load()

    private fun load(): SettingsData = runCatching {
        json.decodeFromString<SettingsData>(file.readText())
    }.getOrDefault(SettingsData())

    private fun save() {
        file.writeText(json.encodeToString(data))
    }

    override var backendUrl: String
        get() = data.backendUrl
        set(value) { data = data.copy(backendUrl = value); save() }

    override var playerCommand: String
        get() = data.playerCommand
        set(value) { data = data.copy(playerCommand = value); save() }

    override var browserCommand: String
        get() = data.browserCommand
        set(value) { data = data.copy(browserCommand = value); save() }
}

actual fun createAppSettings(): AppSettings = DesktopAppSettings()
