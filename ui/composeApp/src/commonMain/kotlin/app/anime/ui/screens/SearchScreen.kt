package app.anime.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import app.anime.data.dto.TitleCardDto
import app.anime.presentation.SearchFilters
import app.anime.presentation.SearchUiState
import app.anime.ui.components.TitleCard

@Composable
fun SearchScreen(
    state: SearchUiState,
    onQueryChange: (String) -> Unit,
    onFilterChange: (SearchFilters) -> Unit,
    onToggleFilters: () -> Unit,
    onTitleClick: (TitleCardDto) -> Unit,
    onLoadMore: () -> Unit,
    modifier: Modifier = Modifier,
    columns: Int = 4,
    onSettingsClick: (() -> Unit)? = null,
) {
    Column(modifier = modifier.fillMaxSize()) {
        // ─── Search bar row ──────────────────────────────────────────────
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
            Spacer(Modifier.width(8.dp))
            // Filter toggle button — highlighted when any filter is active
            IconButton(onClick = onToggleFilters) {
                Icon(
                    imageVector = Icons.Default.FilterList,
                    contentDescription = "Фильтры",
                    tint = if (state.filters.isActive) MaterialTheme.colorScheme.primary
                           else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (onSettingsClick != null) {
                IconButton(onClick = onSettingsClick) {
                    Icon(Icons.Default.Settings, "Настройки")
                }
            }
        }

        // ─── #9 Filter panel (animated) ─────────────────────────────────
        AnimatedVisibility(visible = state.showFilters) {
            FilterPanel(
                filters = state.filters,
                onFilterChange = onFilterChange,
                modifier = Modifier.padding(horizontal = 16.dp).padding(bottom = 8.dp),
            )
        }

        // ─── Content ────────────────────────────────────────────────────
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

                if (state.results.isNotEmpty()) {
                    Text(
                        text = buildString {
                            append("Показано ${state.results.size} из ${state.totalCount}")
                            if (state.filters.isActive) append(" (с фильтрами)")
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                    )
                }
            }
        }
    }
}

/** Compact filter row — year, genre, status, type. */
@Composable
private fun FilterPanel(
    filters: SearchFilters,
    onFilterChange: (SearchFilters) -> Unit,
    modifier: Modifier = Modifier,
) {
    // Local draft state so we don't fire search on every keystroke in year field
    var yearText by remember(filters.year) { mutableStateOf(filters.year?.toString() ?: "") }

    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        tonalElevation = 2.dp,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("Фильтры", style = MaterialTheme.typography.labelLarge)

            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                // Year
                OutlinedTextField(
                    value = yearText,
                    onValueChange = { v ->
                        yearText = v.filter { it.isDigit() }.take(4)
                        val y = yearText.toIntOrNull()
                        onFilterChange(filters.copy(year = y))
                    },
                    label = { Text("Год") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Number,
                        imeAction = ImeAction.Next,
                    ),
                    modifier = Modifier.width(100.dp),
                )

                // Genre
                OutlinedTextField(
                    value = filters.genre,
                    onValueChange = { onFilterChange(filters.copy(genre = it)) },
                    label = { Text("Жанр") },
                    placeholder = { Text("Комедия...") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )

                // Status
                OutlinedTextField(
                    value = filters.status,
                    onValueChange = { onFilterChange(filters.copy(status = it)) },
                    label = { Text("Статус") },
                    placeholder = { Text("Ongoing...") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )

                // Type
                OutlinedTextField(
                    value = filters.type,
                    onValueChange = { onFilterChange(filters.copy(type = it)) },
                    label = { Text("Тип") },
                    placeholder = { Text("TV...") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )

                // Clear filters button
                if (filters.isActive) {
                    OutlinedButton(
                        onClick = { onFilterChange(SearchFilters()) },
                        modifier = Modifier.align(Alignment.CenterVertically),
                    ) {
                        Text("Сбросить")
                    }
                }
            }
        }
    }
}
