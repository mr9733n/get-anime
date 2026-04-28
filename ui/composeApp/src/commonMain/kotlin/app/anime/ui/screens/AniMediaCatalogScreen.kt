package app.anime.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.anime.data.dto.TitleCardDto
import app.anime.presentation.AniMediaCatalogUiState
import app.anime.presentation.ScheduleProviderItemState
import app.anime.ui.components.ClearableOutlinedTextField
import app.anime.ui.components.TitleCard

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun AniMediaCatalogScreen(
    state: AniMediaCatalogUiState,
    onQueryChange: (String) -> Unit,
    onLoadedFilterChange: (Boolean?) -> Unit,
    onTitleClick: (TitleCardDto) -> Unit,
    onProviderItemLoad: (ScheduleProviderItemState) -> Unit,
    onRefresh: () -> Unit,
    onLoadMore: () -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val filteredItems = remember(state.items, state.query, state.showLoadedOnly) {
        state.items.filter { item ->
            val loadedMatches = when (state.showLoadedOnly) {
                true -> item.titleId != null
                false -> item.titleId == null
                null -> true
            }
            loadedMatches && item.matchesQuery(state.query)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Каталог AniMedia") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад")
                    }
                },
                actions = {
                    IconButton(
                        onClick = onRefresh,
                        enabled = !state.isLoading && !state.isLoadingMore,
                    ) {
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

            state.error != null && state.items.isEmpty() -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(state.error, color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = onRefresh) { Text("Повторить") }
                }
            }

            else -> {
                val gridState = rememberLazyGridState()
                LazyVerticalGrid(
                    columns = GridCells.Adaptive(minSize = 150.dp),
                    state = gridState,
                    contentPadding = PaddingValues(
                        start = 12.dp,
                        top = padding.calculateTopPadding() + 12.dp,
                        end = 12.dp,
                        bottom = padding.calculateBottomPadding() + 12.dp,
                    ),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    item(span = { GridItemSpan(maxLineSpan) }) {
                        AniMediaCatalogFilterBar(
                            query = state.query,
                            onQueryChange = onQueryChange,
                            loadedFilter = state.showLoadedOnly,
                            onLoadedFilterChange = onLoadedFilterChange,
                            filteredCount = filteredItems.size,
                            totalCount = state.items.size,
                        )
                    }

                    val actionMessage = state.actionMessage
                    if (!actionMessage.isNullOrBlank()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            Text(
                                text = actionMessage,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(horizontal = 4.dp),
                            )
                        }
                    }

                    if (filteredItems.isEmpty()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 48.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(
                                    text = "По фильтрам ничего не найдено",
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }

                    items(
                        items = filteredItems,
                        key = { it.key },
                    ) { item ->
                        val card = item.toTitleCardDto()
                        val canOpenTitle = item.titleId != null
                        val isLoading = item.key in state.loadingProviderKeys
                        Box(
                            modifier = Modifier.fillMaxWidth(),
                            contentAlignment = Alignment.Center,
                        ) {
                            Box {
                                TitleCard(
                                    title = card,
                                    onClick = { if (canOpenTitle) onTitleClick(it) },
                                    width = 150,
                                    height = 225,
                                    subtitle = listOfNotNull(item.meta, item.episodeLabel)
                                        .joinToString(" · ")
                                        .takeIf { it.isNotBlank() },
                                    subtitleMaxLines = 2,
                                    enabled = canOpenTitle,
                                )
                                if (!canOpenTitle) {
                                    FilledIconButton(
                                        onClick = { onProviderItemLoad(item) },
                                        enabled = !isLoading,
                                        modifier = Modifier
                                            .align(Alignment.TopEnd)
                                            .padding(4.dp),
                                    ) {
                                        if (isLoading) {
                                            CircularProgressIndicator(
                                                modifier = Modifier.size(16.dp),
                                                strokeWidth = 2.dp,
                                                color = MaterialTheme.colorScheme.onPrimary,
                                            )
                                        } else {
                                            Icon(Icons.Default.Add, "Загрузить тайтл")
                                        }
                                    }
                                }
                            }
                        }
                    }

                    item(span = { GridItemSpan(maxLineSpan) }) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 12.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            OutlinedButton(
                                onClick = onLoadMore,
                                enabled = !state.isLoading && !state.isLoadingMore,
                            ) {
                                if (state.isLoadingMore) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(16.dp),
                                        strokeWidth = 2.dp,
                                    )
                                    Spacer(Modifier.width(8.dp))
                                }
                                Text("Загрузить еще")
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AniMediaCatalogFilterBar(
    query: String,
    onQueryChange: (String) -> Unit,
    loadedFilter: Boolean?,
    onLoadedFilterChange: (Boolean?) -> Unit,
    filteredCount: Int,
    totalCount: Int,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = MaterialTheme.shapes.medium,
        tonalElevation = 2.dp,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            ClearableOutlinedTextField(
                value = query,
                onValueChange = onQueryChange,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                leadingIcon = { Icon(Icons.Default.Search, "Поиск") },
                placeholder = { Text("Поиск в каталоге AniMedia...") },
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = loadedFilter == null,
                    onClick = { onLoadedFilterChange(null) },
                    label = { Text("Все") },
                )
                FilterChip(
                    selected = loadedFilter == true,
                    onClick = { onLoadedFilterChange(true) },
                    label = { Text("В базе") },
                )
                FilterChip(
                    selected = loadedFilter == false,
                    onClick = { onLoadedFilterChange(false) },
                    label = { Text("Не загружены") },
                )
            }
            Text(
                text = "Показано $filteredCount из $totalCount",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun ScheduleProviderItemState.toTitleCardDto(): TitleCardDto =
    TitleCardDto(
        titleId = titleId ?: externalTitleId.toIntOrNull() ?: 0,
        nameRu = title,
        posterUrl = posterUrl,
        provider = providerLabel,
    )

private fun ScheduleProviderItemState.matchesQuery(query: String): Boolean {
    val normalized = query.trim().lowercase()
    if (normalized.isEmpty()) return true
    return externalTitleId.contains(normalized, ignoreCase = true) ||
        title.contains(normalized, ignoreCase = true) ||
        providerLabel.contains(normalized, ignoreCase = true) ||
        meta?.contains(normalized, ignoreCase = true) == true ||
        episodeLabel?.contains(normalized, ignoreCase = true) == true
}
