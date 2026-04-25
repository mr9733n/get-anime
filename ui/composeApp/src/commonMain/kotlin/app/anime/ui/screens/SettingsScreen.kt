package app.anime.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.anime.data.AppSettings
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    settings: AppSettings,
    onBack: () -> Unit,
    onConnectionTest: suspend (url: String) -> Boolean,
    modifier: Modifier = Modifier,
) {
    var urlDraft by remember { mutableStateOf(settings.backendUrl) }
    var playerDraft by remember { mutableStateOf(settings.playerCommand) }
    var testResult by remember { mutableStateOf<TestResult?>(null) }
    var isTesting by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Настройки") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад")
                    }
                },
            )
        },
        modifier = modifier,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Text("Backend сервер", style = MaterialTheme.typography.headlineMedium)

            OutlinedTextField(
                value = urlDraft,
                onValueChange = { urlDraft = it },
                label = { Text("URL сервера") },
                placeholder = { Text("http://192.168.1.100:8765") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                supportingText = {
                    Text("Desktop: http://localhost:8765 | TV: адрес PC в локальной сети")
                },
            )

            Row(
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Button(
                    onClick = {
                        settings.backendUrl = urlDraft.trim()
                        testResult = TestResult.Saved
                    }
                ) {
                    Icon(Icons.Default.Done, null)
                    Spacer(Modifier.width(8.dp))
                    Text("Сохранить")
                }

                OutlinedButton(
                    onClick = {
                        isTesting = true
                        testResult = null
                        scope.launch {
                            val ok = runCatching { onConnectionTest(urlDraft.trim()) }
                                .getOrDefault(false)
                            testResult = if (ok) TestResult.Ok else TestResult.Fail
                            isTesting = false
                        }
                    },
                    enabled = !isTesting,
                ) {
                    if (isTesting) {
                        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Default.Refresh, null)
                    }
                    Spacer(Modifier.width(8.dp))
                    Text("Проверить соединение")
                }

                testResult?.let { result ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        when (result) {
                            TestResult.Ok -> {
                                Icon(
                                    Icons.Default.CheckCircle, null,
                                    tint = MaterialTheme.colorScheme.primary,
                                )
                                Spacer(Modifier.width(4.dp))
                                Text("Подключено", color = MaterialTheme.colorScheme.primary)
                            }
                            TestResult.Fail -> {
                                Icon(
                                    Icons.Default.Warning, null,
                                    tint = MaterialTheme.colorScheme.error,
                                )
                                Spacer(Modifier.width(4.dp))
                                Text("Нет ответа", color = MaterialTheme.colorScheme.error)
                            }
                            TestResult.Saved -> {
                                Icon(Icons.Default.Done, null)
                                Spacer(Modifier.width(4.dp))
                                Text("Сохранено")
                            }
                        }
                    }
                }
            }

            HorizontalDivider()

            PlayerSettingsSection(
                playerDraft = playerDraft,
                onPlayerChange = { playerDraft = it },
                onSave = { settings.playerCommand = playerDraft.trim() },
            )
        }
    }
}

@Composable
expect fun PlayerSettingsSection(
    playerDraft: String,
    onPlayerChange: (String) -> Unit,
    onSave: () -> Unit,
)

private enum class TestResult { Ok, Fail, Saved }
