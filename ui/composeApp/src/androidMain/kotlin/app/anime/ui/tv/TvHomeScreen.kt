package app.anime.ui.tv

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.tv.material3.*
import app.anime.data.dto.TitleCardDto
import app.anime.presentation.HomeUiState
import app.anime.ui.components.TvTitleCard

/**
 * Android TV home screen — schedule rows, Netflix-style layout.
 * Fully D-pad navigable.
 */
@OptIn(ExperimentalTvMaterial3Api::class)
@Composable
fun TvHomeScreen(
    state: HomeUiState,
    onTitleClick: (TitleCardDto) -> Unit,
    onSearchClick: () -> Unit,
    onRefresh: () -> Unit,
    onSettingsClick: () -> Unit = {},
    onScheduleClick: () -> Unit = {},
) {
    if (state.isLoading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        return
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(start = 48.dp, top = 24.dp, end = 24.dp, bottom = 24.dp),
    ) {
        // Top bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "Anime Player",
                style = MaterialTheme.typography.headlineLarge,
                color = Color.White,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = onSearchClick) {
                    Icon(Icons.Default.Search, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Поиск")
                }
                Button(onClick = onScheduleClick) {
                    Icon(Icons.Default.DateRange, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Расписание")
                }
                Button(onClick = onRefresh) {
                    Icon(Icons.Default.Refresh, contentDescription = null)
                }
                Button(onClick = onSettingsClick) {
                    Icon(Icons.Default.Settings, contentDescription = null)
                }
            }
        }

        Spacer(Modifier.height(24.dp))

        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(32.dp),
        ) {
            // Today's schedule
            if (state.todaySchedule.isNotEmpty()) {
                item {
                    TvContentRow(
                        title = "Сегодня",
                        // Schedule entries don't carry card data yet — need to batch-load titles
                        // For now show placeholder cards with just title_id
                        items = state.todaySchedule.map {
                            TitleCardDto(titleId = it.titleId)
                        },
                        onItemClick = onTitleClick,
                    )
                }
            }

            // Tomorrow's schedule
            if (state.tomorrowSchedule.isNotEmpty()) {
                item {
                    TvContentRow(
                        title = "Завтра",
                        items = state.tomorrowSchedule.map {
                            TitleCardDto(titleId = it.titleId)
                        },
                        onItemClick = onTitleClick,
                    )
                }
            }

            if (state.error != null) {
                item {
                    Text(
                        text = "Ошибка: ${state.error}",
                        color = Color.Red,
                        modifier = Modifier.padding(16.dp),
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalTvMaterial3Api::class)
@Composable
fun TvContentRow(
    title: String,
    items: List<TitleCardDto>,
    onItemClick: (TitleCardDto) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier) {
        Text(
            text = title,
            style = MaterialTheme.typography.headlineMedium,
            color = Color.White,
            modifier = Modifier.padding(bottom = 12.dp),
        )
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(items, key = { it.titleId }) { card ->
                TvTitleCard(title = card, onClick = onItemClick)
            }
        }
    }
}
