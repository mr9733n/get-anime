package app.anime.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.anime.ui.components.ClearableOutlinedTextField
import kotlinx.coroutines.delay

@Composable
actual fun PlayerSettingsSection(
    playerDraft: String,
    onPlayerChange: (String) -> Unit,
    onSave: () -> Unit,
    browserDraft: String,
    onBrowserChange: (String) -> Unit,
    onBrowserSave: () -> Unit,
) {
    // ── Video player ──────────────────────────────────────────────────────────
    var playerSaved by remember { mutableStateOf(false) }

    Text("Плеер", style = MaterialTheme.typography.headlineMedium)

    ClearableOutlinedTextField(
        value = playerDraft,
        onValueChange = onPlayerChange,
        label = { Text("Команда плеера") },
        placeholder = { Text("mpv") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
        supportingText = {
            Text("Команда для запуска видео: mpv, vlc, или полный путь")
        },
    )

    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Button(onClick = {
            onSave()
            playerSaved = true
        }) {
            Text("Сохранить")
        }

        // #6 fix: auto-hide confirmation after 2 seconds
        if (playerSaved) {
            LaunchedEffect(Unit) {
                delay(2_000)
                playerSaved = false
            }
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
                Text(
                    "Сохранено",
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }

    Spacer(Modifier.height(16.dp))

    // ── Browser (for web-player page URLs) ───────────────────────────────────
    var browserSaved by remember { mutableStateOf(false) }

    Text("Браузер", style = MaterialTheme.typography.headlineMedium)

    ClearableOutlinedTextField(
        value = browserDraft,
        onValueChange = onBrowserChange,
        label = { Text("Команда браузера") },
        placeholder = { Text("(системный браузер)") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
        supportingText = {
            Text("Открывает ссылки вебплеера. Оставьте пустым для браузера по умолчанию")
        },
    )

    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Button(onClick = {
            onBrowserSave()
            browserSaved = true
        }) {
            Text("Сохранить")
        }

        if (browserSaved) {
            LaunchedEffect(Unit) {
                delay(2_000)
                browserSaved = false
            }
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
                Text(
                    "Сохранено",
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}
