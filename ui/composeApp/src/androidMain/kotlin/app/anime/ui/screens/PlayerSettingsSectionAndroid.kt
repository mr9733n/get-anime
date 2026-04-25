package app.anime.ui.screens

import androidx.compose.runtime.Composable

@Composable
actual fun PlayerSettingsSection(
    playerDraft: String,
    onPlayerChange: (String) -> Unit,
    onSave: () -> Unit,
    browserDraft: String,
    onBrowserChange: (String) -> Unit,
    onBrowserSave: () -> Unit,
) {
    // Android uses system video/browser intents — no command settings needed
}
