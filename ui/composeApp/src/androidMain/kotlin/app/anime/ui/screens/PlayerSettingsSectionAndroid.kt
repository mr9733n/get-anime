package app.anime.ui.screens

import androidx.compose.runtime.Composable

@Composable
actual fun PlayerSettingsSection(
    playerDraft: String,
    onPlayerChange: (String) -> Unit,
    onSave: () -> Unit,
) {
    // Android uses system video player intents — no player command setting needed
}
