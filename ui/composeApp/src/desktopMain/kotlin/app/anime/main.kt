package app.anime

import androidx.compose.runtime.*
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.*
import app.anime.data.AnimeRepository
import app.anime.data.AppSettings
import app.anime.data.HttpBackendClient
import app.anime.data.createAppSettings

fun main() = application {
    val settings = remember { createAppSettings() }

    // Create client from saved settings; recreate when URL changes
    var backendUrl by remember { mutableStateOf(settings.backendUrl) }
    val backendClient = remember(backendUrl) { HttpBackendClient(backendUrl) }
    val repo = remember(backendClient) { AnimeRepository(backendClient) }

    DisposableEffect(backendClient) {
        onDispose { backendClient.close() }
    }

    Window(
        onCloseRequest = ::exitApplication,
        title = "Anime Player",
        state = rememberWindowState(width = 1280.dp, height = 800.dp),
    ) {
        DesktopApp(
            repo = repo,
            settings = settings,
            onBackendUrlChange = { newUrl ->
                settings.backendUrl = newUrl
                backendUrl = newUrl
            },
        )
    }
}
