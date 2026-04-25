package app.anime.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.anime.data.dto.TitleCardDto
import app.anime.presentation.SearchUiState
import app.anime.ui.components.TitleCard

@Composable
fun SearchScreen(
    state: SearchUiState,
    onQueryChange: (String) -> Unit,
    onTitleClick: (TitleCardDto) -> Unit,
    onLoadMore: () -> Unit,
    modifier: Modifier = Modifier,
    columns: Int = 4,
    onSettingsClick: (() -> Unit)? = null,
) {
    Column(modifier = modifier.fillMaxSize()) {
        // Search bar + optional settings icon
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = state.query,
                onValueChange = onQueryChange,
                placeholder = { Text("Поиск аниме...") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            if (onSettingsClick != null) {
                Spacer(Modifier.width(8.dp))
                IconButton(onClick = onSettingsClick) {
                    Icon(Icons.Default.Settings, "Настройки")
                }
            }
        }

        when {
            state.isLoading && state.results.isEmpty() -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }

            state.error != null && state.results.isEmpty() -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = "Ошибка: ${state.error}",
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }

            else -> {
                val gridState = rememberLazyGridState()

                // Infinite scroll — load more when near the end
                LaunchedEffect(gridState) {
                    snapshotFlow { gridState.layoutInfo }
                        .collect { info ->
                            val lastVisible = info.visibleItemsInfo.lastOrNull()?.index ?: 0
                            val total = info.totalItemsCount
                            if (total > 0 && lastVisible >= total - columns * 2) {
                                onLoadMore()
                            }
                        }
                }

                LazyVerticalGrid(
                    columns = GridCells.Fixed(columns),
                    state = gridState,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.weight(1f),
                ) {
                    items(
                        items = state.results,
                        key = { it.titleId },
                    ) { title ->
                        TitleCard(title = title, onClick = onTitleClick)
                    }

                    if (state.isLoading) {
                        item(span = { GridItemSpan(columns) }) {
                            Box(
                                Modifier.fillMaxWidth().padding(16.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                CircularProgressIndicator(Modifier.size(24.dp))
                            }
                        }
                    }
                }

                // Status bar
                if (state.results.isNotEmpty()) {
                    Text(
                        text = "Показано ${state.results.size} из ${state.totalCount}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                    )
                }
            }
        }
    }
}
