package app.anime.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay

@Composable
actual fun PlayerSettingsSection(
    playerDraft: String,
    onPlayerChange: (String) -> Unit,
    onSave: () -> Unit,
) {
    // #6 fix: show a brief "Сохранено" confirmation after clicking Save
    var saved by remember { mutableStateOf(false) }

    Text("Плеер", style = MaterialTheme.typography.headlineMedium)

    OutlinedTextField(
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
            saved = true
        }) {
            Text("Сохранить")
        }

        // Auto-hide the confirmation after 2 seconds
        if (saved) {
            LaunchedEffect(Unit) {
                delay(2_000)
                saved = false
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
