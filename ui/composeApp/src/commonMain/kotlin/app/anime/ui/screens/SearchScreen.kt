package app.anime.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
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
import app.anime.ui.components.ClearableOutlinedTextField
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
    onScheduleClick: (() -> Unit)? = null,
    onAniMediaCatalogClick: (() -> Unit)? = null,
    onSettingsClick: (() -> Unit)? = null,
    onProviderLoad: (String, String, Boolean, Int) -> Unit = { _, _, _, _ -> },
    onRandomAniLibertyClick: (() -> Unit)? = null,
) {
    Column(modifier = modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ClearableOutlinedTextField(
                value = state.query,
                onValueChange = onQueryChange,
                placeholder = { Text("\u041f\u043e\u0438\u0441\u043a \u0430\u043d\u0438\u043c\u0435...") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            IconButton(onClick = onToggleFilters) {
                Icon(
                    imageVector = Icons.Default.FilterList,
                    contentDescription = "\u0424\u0438\u043b\u044c\u0442\u0440\u044b",
                    tint = if (state.filters.isActive) MaterialTheme.colorScheme.primary
                           else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (onRandomAniLibertyClick != null) {
                IconButton(
                    onClick = onRandomAniLibertyClick,
                    enabled = !state.randomLoadInProgress,
                ) {
                    if (state.randomLoadInProgress) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Icon(Icons.Default.Star, "\u0421\u043b\u0443\u0447\u0430\u0439\u043d\u044b\u0439 AniLiberty")
                    }
                }
            }
            if (onScheduleClick != null) {
                IconButton(onClick = onScheduleClick) {
                    Icon(Icons.Default.DateRange, "\u0420\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u0435")
                }
            }
            if (onAniMediaCatalogClick != null) {
                IconButton(onClick = onAniMediaCatalogClick) {
                    Icon(Icons.AutoMirrored.Filled.List, "Каталог AniMedia")
                }
            }
            if (onSettingsClick != null) {
                IconButton(onClick = onSettingsClick) {
                    Icon(Icons.Default.Settings, "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438")
                }
            }
        }

        AnimatedVisibility(visible = state.showFilters) {
            FilterPanel(
                filters = state.filters,
                onFilterChange = onFilterChange,
                modifier = Modifier.padding(horizontal = 16.dp).padding(bottom = 8.dp),
            )
        }

        if (!state.facetTitle.isNullOrBlank()) {
            Surface(
                modifier = Modifier.padding(horizontal = 16.dp).padding(bottom = 8.dp),
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.secondaryContainer,
                contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
            ) {
                Text(
                    text = state.facetTitle,
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                )
            }
        }

        if (!state.randomLoadError.isNullOrBlank()) {
            Text(
                text = "\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043b\u0443\u0447\u0430\u0439\u043d\u043e\u0433\u043e \u0442\u0430\u0439\u0442\u043b\u0430: ${state.randomLoadError}",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
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
                        text = "\u041e\u0448\u0438\u0431\u043a\u0430: ${state.error}",
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }

            state.results.isEmpty() &&
                (state.query.isNotBlank() || state.filters.isActive ||
                    (state.watchlist.isEmpty() && state.recentTitles.isEmpty())) -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text(
                            text = when {
                                state.query.isNotBlank() ->
                                    "\u041f\u043e \u0437\u0430\u043f\u0440\u043e\u0441\u0443 \"${state.query}\" \u043d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e"
                                state.filters.isActive ->
                                    "\u041f\u043e \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u043c \u0444\u0438\u043b\u044c\u0442\u0440\u0430\u043c \u043d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e"
                                else ->
                                    "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0437\u0430\u043f\u0440\u043e\u0441 \u0434\u043b\u044f \u043f\u043e\u0438\u0441\u043a\u0430"
                            },
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (state.query.isNotBlank()) {
                            ProviderLoadControls(
                                defaultQuery = state.query,
                                loadingProvider = state.providerLoadInProgress,
                                error = state.providerLoadError,
                                onProviderLoad = onProviderLoad,
                            )
                        }
                    }
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
                    columns = GridCells.Adaptive(minSize = 150.dp),
                    state = gridState,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.weight(1f),
                ) {
                    if (state.query.isBlank() && !state.filters.isActive && state.recentTitles.isNotEmpty()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            TitleRail(
                                title = "\u041d\u0435\u0434\u0430\u0432\u043d\u043e \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u043e",
                                titles = state.recentTitles,
                                onTitleClick = onTitleClick,
                            )
                        }
                    }

                    if (state.query.isBlank() && !state.filters.isActive && state.watchlist.isNotEmpty()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            TitleRail(
                                title = "\u0425\u043e\u0447\u0443 \u043f\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u0442\u044c",
                                titles = state.watchlist,
                                onTitleClick = onTitleClick,
                            )
                        }
                    }

                    if (state.query.isNotBlank()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            ProviderLoadControls(
                                defaultQuery = state.query,
                                loadingProvider = state.providerLoadInProgress,
                                error = state.providerLoadError,
                                onProviderLoad = onProviderLoad,
                            )
                        }
                    }

                    items(
                        items = state.results,
                        key = { it.titleId },
                    ) { title ->
                        Box(
                            modifier = Modifier.fillMaxWidth(),
                            contentAlignment = Alignment.Center,
                        ) {
                            TitleCard(
                                title = title,
                                onClick = onTitleClick,
                                width = 150,
                                height = 225,
                            )
                        }
                    }

                    if (state.isLoading) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
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
                            append("\u041f\u043e\u043a\u0430\u0437\u0430\u043d\u043e ${state.results.size} \u0438\u0437 ${state.totalCount}")
                            if (state.filters.isActive) append(" (\u0441 \u0444\u0438\u043b\u044c\u0442\u0440\u0430\u043c\u0438)")
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

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun TitleRail(
    title: String,
    titles: List<TitleCardDto>,
    onTitleClick: (TitleCardDto) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(horizontal = 4.dp),
        )
        FlowRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            titles.forEach { titleCard ->
                TitleCard(
                    title = titleCard,
                    onClick = onTitleClick,
                    width = 130,
                    height = 195,
                )
            }
        }
    }
}

@Composable
private fun ProviderLoadControls(
    defaultQuery: String,
    loadingProvider: String?,
    error: String?,
    onProviderLoad: (String, String, Boolean, Int) -> Unit,
) {
    var providerQuery by remember(defaultQuery) { mutableStateOf(defaultQuery) }
    var byExternalId by remember { mutableStateOf(false) }
    var limit by remember { mutableStateOf(1) }

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        ClearableOutlinedTextField(
            value = providerQuery,
            onValueChange = { providerQuery = it },
            label = {
                Text(
                    if (byExternalId) {
                        "External ID"
                    } else {
                        "\u0423\u0442\u043e\u0447\u043d\u0438\u0442\u044c \u0437\u0430\u043f\u0440\u043e\u0441"
                    }
                )
            },
            singleLine = true,
            enabled = loadingProvider == null,
            modifier = Modifier
                .fillMaxWidth(0.56f)
                .widthIn(min = 280.dp, max = 560.dp),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ModeButton(
                selected = !byExternalId,
                text = "\u041f\u043e \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044e",
                enabled = loadingProvider == null,
                onClick = { byExternalId = false },
            )
            ModeButton(
                selected = byExternalId,
                text = "\u041f\u043e ID",
                enabled = loadingProvider == null,
                onClick = {
                    byExternalId = true
                    limit = 1
                },
            )
            if (!byExternalId) {
                ModeButton(
                    selected = limit == 1,
                    text = "1",
                    enabled = loadingProvider == null,
                    onClick = { limit = 1 },
                )
                ModeButton(
                    selected = limit == 3,
                    text = "\u0434\u043e 3",
                    enabled = loadingProvider == null,
                    onClick = { limit = 3 },
                )
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ProviderLoadButton(
                providerCode = "aniliberty",
                label = "\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0438\u0437 AniLiberty",
                providerQuery = providerQuery,
                byExternalId = byExternalId,
                limit = limit,
                loadingProvider = loadingProvider,
                onProviderLoad = onProviderLoad,
            )
            ProviderLoadButton(
                providerCode = "animedia",
                label = "\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0438\u0437 AniMedia",
                providerQuery = providerQuery,
                byExternalId = byExternalId,
                limit = limit,
                loadingProvider = loadingProvider,
                onProviderLoad = onProviderLoad,
            )
        }
        if (!error.isNullOrBlank()) {
            Text(
                text = "\u041e\u0448\u0438\u0431\u043a\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438: $error",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun ProviderLoadButton(
    providerCode: String,
    label: String,
    providerQuery: String,
    byExternalId: Boolean,
    limit: Int,
    loadingProvider: String?,
    onProviderLoad: (String, String, Boolean, Int) -> Unit,
) {
    val isLoading = loadingProvider == providerCode
    OutlinedButton(
        onClick = { onProviderLoad(providerCode, providerQuery, byExternalId, limit) },
        enabled = loadingProvider == null && providerQuery.isNotBlank(),
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp),
                    strokeWidth = 2.dp,
                )
            }
            Text(label)
        }
    }
}

@Composable
private fun ModeButton(
    selected: Boolean,
    text: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer
                             else MaterialTheme.colorScheme.surface,
            contentColor = if (selected) MaterialTheme.colorScheme.onPrimaryContainer
                           else MaterialTheme.colorScheme.onSurfaceVariant,
        ),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Text(text)
    }
}

@Composable
private fun FilterPanel(
    filters: SearchFilters,
    onFilterChange: (SearchFilters) -> Unit,
    modifier: Modifier = Modifier,
) {
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
            Text("\u0424\u0438\u043b\u044c\u0442\u0440\u044b", style = MaterialTheme.typography.labelLarge)
            ActiveFacetSummary(filters = filters)

            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                ClearableOutlinedTextField(
                    value = yearText,
                    onValueChange = { v ->
                        yearText = v.filter { it.isDigit() }.take(4)
                        onFilterChange(filters.copy(year = yearText.toIntOrNull()))
                    },
                    label = { Text("\u0413\u043e\u0434") },
                    singleLine = true,
                    keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                        keyboardType = KeyboardType.Number,
                        imeAction = ImeAction.Next,
                    ),
                    modifier = Modifier.width(100.dp),
                )

                ClearableOutlinedTextField(
                    value = filters.genre,
                    onValueChange = { onFilterChange(filters.copy(genre = it)) },
                    label = { Text("\u0416\u0430\u043d\u0440") },
                    placeholder = { Text("\u041a\u043e\u043c\u0435\u0434\u0438\u044f...") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )

                ClearableOutlinedTextField(
                    value = filters.status,
                    onValueChange = { onFilterChange(filters.copy(status = it)) },
                    label = { Text("\u0421\u0442\u0430\u0442\u0443\u0441") },
                    placeholder = { Text("Ongoing...") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )

                ClearableOutlinedTextField(
                    value = filters.type,
                    onValueChange = { onFilterChange(filters.copy(type = it)) },
                    label = { Text("\u0422\u0438\u043f") },
                    placeholder = { Text("TV...") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )

                if (filters.teamMember.isNotBlank()) {
                    ReadOnlyFilterChip(
                        label = "Команда",
                        value = filters.teamMember,
                        modifier = Modifier.align(Alignment.CenterVertically),
                    )
                }

                if (filters.franchise.isNotBlank()) {
                    ReadOnlyFilterChip(
                        label = "Франшиза",
                        value = filters.franchise,
                        modifier = Modifier.align(Alignment.CenterVertically),
                    )
                }

                if (filters.isActive) {
                    OutlinedButton(
                        onClick = { onFilterChange(SearchFilters()) },
                        modifier = Modifier.align(Alignment.CenterVertically),
                    ) {
                        Text("\u0421\u0431\u0440\u043e\u0441\u0438\u0442\u044c")
                    }
                }
            }
        }
    }
}

@Composable
private fun ActiveFacetSummary(filters: SearchFilters) {
    val parts = listOfNotNull(
        filters.year?.let { "Год: $it" },
        filters.genre.takeIf { it.isNotBlank() }?.let { "Жанр: $it" },
        filters.status.takeIf { it.isNotBlank() }?.let { "Статус: $it" },
        filters.type.takeIf { it.isNotBlank() }?.let { "Тип: $it" },
        filters.teamMember.takeIf { it.isNotBlank() }?.let { "Команда: $it" },
        filters.franchise.takeIf { it.isNotBlank() }?.let { "Франшиза: $it" },
    )
    if (parts.isEmpty()) return
    Text(
        text = parts.joinToString(" · "),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun ReadOnlyFilterChip(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    Surface(
        shape = MaterialTheme.shapes.small,
        color = MaterialTheme.colorScheme.secondaryContainer,
        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
        modifier = modifier,
    ) {
        Text(
            text = "$label: $value",
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            maxLines = 1,
        )
    }
}
