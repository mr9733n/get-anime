package app.anime.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import app.anime.data.dto.ScheduleEntryDto
import app.anime.data.dto.TitleCardDto
import app.anime.presentation.ScheduleProviderItemState
import app.anime.presentation.ScheduleUiState
import app.anime.ui.components.ClearableOutlinedTextField
import app.anime.ui.components.TitleCard

/**
 * #8: Full-week schedule screen (Desktop / common).
 * Shows each day with a horizontal row of title cards.
 */
@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun ScheduleScreen(
    state: ScheduleUiState,
    onTitleClick: (TitleCardDto) -> Unit,
    onProviderItemLoad: (ScheduleProviderItemState) -> Unit,
    onRefresh: () -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var providerFilter by remember { mutableStateOf(ScheduleProviderFilter.All) }
    var releaseFilter by remember { mutableStateOf(ScheduleReleaseFilter.All) }
    var query by remember { mutableStateOf("") }

    val filteredDays = remember(state.days, providerFilter, releaseFilter, query) {
        state.days
            .map { day ->
                day.copy(entries = day.entries.filter { it.matchesFilters(providerFilter, releaseFilter, query) })
            }
            .filter { it.entries.isNotEmpty() }
    }
    val filteredTodayItems = remember(state.todayItems, providerFilter, releaseFilter, query) {
        state.todayItems.filter { it.matchesFilters(providerFilter, releaseFilter, query) }
    }
    val filteredAnnouncementItems = remember(state.announcementItems, providerFilter, releaseFilter, query) {
        state.announcementItems.filter { it.matchesFilters(providerFilter, releaseFilter, query) }
    }
    val filteredOtherItems = remember(state.otherProviderItems, providerFilter, releaseFilter, query) {
        state.otherProviderItems.filter { it.matchesFilters(providerFilter, releaseFilter, query) }
    }

    val totalCount =
        state.days.sumOf { it.entries.size } +
            state.todayItems.size +
            state.announcementItems.size +
            state.otherProviderItems.size
    val filteredCount =
        filteredDays.sumOf { it.entries.size } +
            filteredTodayItems.size +
            filteredAnnouncementItems.size +
            filteredOtherItems.size

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
                    IconButton(
                        onClick = onRefresh,
                        enabled = !state.isLoading,
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

            state.days.isEmpty() &&
                state.todayItems.isEmpty() &&
                state.announcementItems.isEmpty() &&
                state.otherProviderItems.isEmpty() -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { Text("Расписание пусто", color = MaterialTheme.colorScheme.onSurfaceVariant) }

            else -> LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp),
            ) {
                item(key = "schedule-filters") {
                    ScheduleFilterBar(
                        query = query,
                        onQueryChange = { query = it },
                        providerFilter = providerFilter,
                        onProviderFilterChange = { providerFilter = it },
                        releaseFilter = releaseFilter,
                        onReleaseFilterChange = { releaseFilter = it },
                        filteredCount = filteredCount,
                        totalCount = totalCount,
                    )
                }

                val actionMessage = state.actionMessage
                if (!actionMessage.isNullOrBlank()) {
                    item(key = "schedule-action-message") {
                        Text(
                            text = actionMessage,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 16.dp),
                        )
                    }
                }

                if (
                    filteredDays.isEmpty() &&
                    filteredTodayItems.isEmpty() &&
                    filteredAnnouncementItems.isEmpty() &&
                    filteredOtherItems.isEmpty()
                ) {
                    item(key = "schedule-filter-empty") {
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

                if (filteredTodayItems.isNotEmpty()) {
                    item(key = "today-provider-items") {
                        ProviderItemsSection(
                            title = "\u0421\u0435\u0433\u043e\u0434\u043d\u044f \u0432\u044b\u0439\u0434\u0443\u0442",
                            items = filteredTodayItems,
                            onTitleClick = onTitleClick,
                            onProviderItemLoad = onProviderItemLoad,
                            loadingProviderKeys = state.loadingProviderKeys,
                        )
                    }
                }

                if (filteredAnnouncementItems.isNotEmpty()) {
                    item(key = "announcement-provider-items") {
                        ProviderItemsSection(
                            title = "\u0410\u043d\u043e\u043d\u0441\u044b",
                            items = filteredAnnouncementItems,
                            onTitleClick = onTitleClick,
                            onProviderItemLoad = onProviderItemLoad,
                            loadingProviderKeys = state.loadingProviderKeys,
                        )
                    }
                }

                items(filteredDays, key = { it.day }) { dayState ->
                    Column {
                        Text(
                            text = dayState.dayName,
                            style = MaterialTheme.typography.headlineSmall,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                        )
                        FlowRow(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 12.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            dayState.entries.forEach { entry ->
                                key(entry.titleId) {
                                    TitleCard(
                                        title = entry.title ?: TitleCardDto(titleId = entry.titleId),
                                        onClick = onTitleClick,
                                        width = 150,
                                        height = 225,
                                        subtitle = "\u0412\u044b\u0445\u043e\u0434\u0438\u0442: ${dayState.dayName}",
                                        subtitleMaxLines = 2,
                                    )
                                }
                            }
                        }
                    }
                }

                if (filteredOtherItems.isNotEmpty()) {
                    item(key = "other-provider-items") {
                        ProviderItemsSection(
                            title = "\u041f\u0440\u043e\u0447\u0435\u0435 \u043e\u0442 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u043e\u0432",
                            items = filteredOtherItems,
                            onTitleClick = onTitleClick,
                            onProviderItemLoad = onProviderItemLoad,
                            loadingProviderKeys = state.loadingProviderKeys,
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ProviderItemsSection(
    title: String,
    items: List<ScheduleProviderItemState>,
    onTitleClick: (TitleCardDto) -> Unit,
    onProviderItemLoad: (ScheduleProviderItemState) -> Unit,
    loadingProviderKeys: Set<String>,
) {
    Column {
        Text(
            text = title,
            style = MaterialTheme.typography.headlineSmall,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
        )
        FlowRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items.forEach { item ->
                key("${item.providerCode}:${item.externalTitleId}") {
                    val titleCard = item.toTitleCardDto()
                    val canOpenTitle = item.titleId != null
                    val isLoading = item.key in loadingProviderKeys
                    Box {
                        TitleCard(
                            title = titleCard,
                            onClick = { if (canOpenTitle) onTitleClick(it) },
                            width = 150,
                            height = 225,
                            subtitle = listOfNotNull(item.meta, item.episodeLabel)
                                .joinToString(" \u00b7 ")
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
                                    Icon(Icons.Default.Add, contentDescription = "Загрузить тайтл")
                                }
                            }
                        }
                    }
                }
            }
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

private enum class ScheduleProviderFilter(val label: String) {
    All("\u0412\u0441\u0435"),
    AniLiberty("AniLiberty"),
    AniMedia("AniMedia"),
}

private enum class ScheduleReleaseFilter(val label: String) {
    All("\u0412\u0441\u0435"),
    Released("\u0412\u044b\u0448\u043b\u0438"),
    Announcements("\u0410\u043d\u043e\u043d\u0441\u044b"),
}

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
private fun ScheduleFilterBar(
    query: String,
    onQueryChange: (String) -> Unit,
    providerFilter: ScheduleProviderFilter,
    onProviderFilterChange: (ScheduleProviderFilter) -> Unit,
    releaseFilter: ScheduleReleaseFilter,
    onReleaseFilterChange: (ScheduleReleaseFilter) -> Unit,
    filteredCount: Int,
    totalCount: Int,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp),
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
                leadingIcon = {
                    Icon(
                        imageVector = Icons.Default.Search,
                        contentDescription = "\u041f\u043e\u0438\u0441\u043a",
                    )
                },
                placeholder = {
                    Text("\u041f\u043e\u0438\u0441\u043a \u0432 \u0440\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u0438...")
                },
            )

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ScheduleProviderFilter.entries.forEach { filter ->
                    FilterChip(
                        selected = providerFilter == filter,
                        onClick = { onProviderFilterChange(filter) },
                        label = { Text(filter.label) },
                    )
                }
            }

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ScheduleReleaseFilter.entries.forEach { filter ->
                    FilterChip(
                        selected = releaseFilter == filter,
                        onClick = { onReleaseFilterChange(filter) },
                        label = { Text(filter.label) },
                    )
                }
            }

            Text(
                text = "\u041f\u043e\u043a\u0430\u0437\u0430\u043d\u043e $filteredCount \u0438\u0437 $totalCount",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun ScheduleEntryDto.matchesFilters(
    providerFilter: ScheduleProviderFilter,
    releaseFilter: ScheduleReleaseFilter,
    query: String,
): Boolean {
    if (releaseFilter == ScheduleReleaseFilter.Announcements) return false
    if (!providerFilter.matchesProvider(title?.provider)) return false

    val normalizedQuery = query.trim().lowercase()
    if (normalizedQuery.isEmpty()) return true

    val title = title
    return titleId.toString().contains(normalizedQuery) ||
        title?.nameRu.containsQuery(normalizedQuery) ||
        title?.nameEn.containsQuery(normalizedQuery) ||
        title?.provider.containsQuery(normalizedQuery) ||
        title?.year?.toString().containsQuery(normalizedQuery) ||
        title?.type.containsQuery(normalizedQuery) ||
        title?.status.containsQuery(normalizedQuery) ||
        title?.genres.orEmpty().any { it.containsQuery(normalizedQuery) }
}

private fun ScheduleProviderItemState.matchesFilters(
    providerFilter: ScheduleProviderFilter,
    releaseFilter: ScheduleReleaseFilter,
    query: String,
): Boolean {
    if (!providerFilter.matchesProvider(providerCode)) return false
    if (!releaseFilter.matchesProviderItem(this)) return false

    val normalizedQuery = query.trim().lowercase()
    if (normalizedQuery.isEmpty()) return true

    return externalTitleId.containsQuery(normalizedQuery) ||
        title.containsQuery(normalizedQuery) ||
        providerLabel.containsQuery(normalizedQuery) ||
        meta.containsQuery(normalizedQuery) ||
        episodeLabel.containsQuery(normalizedQuery) ||
        airDt.containsQuery(normalizedQuery)
}

private fun ScheduleProviderFilter.matchesProvider(provider: String?): Boolean =
    when (this) {
        ScheduleProviderFilter.All -> true
        ScheduleProviderFilter.AniLiberty -> provider?.matchesAnyProviderName("aniliberty", "anilibria", "libr") == true
        ScheduleProviderFilter.AniMedia -> provider?.contains("animedia", ignoreCase = true) == true
    }

private fun ScheduleReleaseFilter.matchesProviderItem(item: ScheduleProviderItemState): Boolean =
    when (this) {
        ScheduleReleaseFilter.All -> true
        ScheduleReleaseFilter.Released -> !item.isAnnouncement
        ScheduleReleaseFilter.Announcements -> item.isAnnouncement
    }

private val ScheduleProviderItemState.isAnnouncement: Boolean
    get() =
        section.equals("announcement", ignoreCase = true) ||
            meta?.contains("Новая серия", ignoreCase = true) == true

private fun String?.containsQuery(query: String): Boolean =
    this?.lowercase()?.contains(query) == true

private fun String.matchesAnyProviderName(vararg needles: String): Boolean =
    needles.any { contains(it, ignoreCase = true) }
