package app.anime.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.anime.data.dto.TitleCardDto
import app.anime.presentation.ScheduleUiState
import app.anime.ui.components.TitleCard

/**
 * #8: Full-week schedule screen (Desktop / common).
 * Shows each day with a horizontal row of title cards.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScheduleScreen(
    state: ScheduleUiState,
    onTitleClick: (TitleCardDto) -> Unit,
    onRefresh: () -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Расписание выхода") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад")
                    }
                },
                actions = {
                    IconButton(onClick = onRefresh) {
                        Icon(Icons.Default.Refresh, "Обновить")
                    }
                },
            )
        },
        modifier = modifier,
    ) { padding ->
        when {
            state.isLoading -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator() }

            state.error != null -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(state.error, color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = onRefresh) { Text("Повторить") }
                }
            }

            state.days.isEmpty() -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { Text("Расписание пусто", color = MaterialTheme.colorScheme.onSurfaceVariant) }

            else -> LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp),
            ) {
                items(state.days, key = { it.day }) { dayState ->
                    Column {
                        Text(
                            text = dayState.dayName,
                            style = MaterialTheme.typography.headlineSmall,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                        )
                        LazyRow(
                            contentPadding = PaddingValues(horizontal = 12.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            items(dayState.entries, key = { it.titleId }) { entry ->
                                TitleCard(
                                    title = TitleCardDto(titleId = entry.titleId),
                                    onClick = onTitleClick,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
