package app.anime.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
actual fun PlayerSettingsSection(
    playerDraft: String,
    onPlayerChange: (String) -> Unit,
    onSave: () -> Unit,
) {
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

    Button(onClick = onSave) {
        Text("Сохранить")
    }
}
