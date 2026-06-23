package app.anime.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.anime.data.AnimeRepository
import app.anime.data.dto.ScheduleEntryDto
import app.anime.data.dto.ScheduleProviderItemDto
import kotlinx.datetime.Clock
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive

data class ScheduleDayState(
    val day: Int,
    val dayName: String,
    val entries: List<ScheduleEntryDto> = emptyList(),
)

data class ScheduleUiState(
    val days: List<ScheduleDayState> = emptyList(),
    val todayItems: List<ScheduleProviderItemState> = emptyList(),
    val announcementItems: List<ScheduleProviderItemState> = emptyList(),
    val otherProviderItems: List<ScheduleProviderItemState> = emptyList(),
    val loadingProviderKeys: Set<String> = emptySet(),
    val actionMessage: String? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
)

data class ScheduleProviderItemState(
    val titleId: Int? = null,
    val providerCode: String,
    val externalTitleId: String,
    val title: String,
    val meta: String? = null,
    val episodeLabel: String? = null,
    val posterUrl: String? = null,
    val titleUrl: String? = null,
    val dayOfWeek: Int? = null,
    val airDt: String? = null,
    val section: String? = null,
) {
    val key: String
        get() = "$providerCode:$externalTitleId"

    val providerLabel: String
        get() = when (providerCode.lowercase()) {
            "aniliberty" -> "AniLiberty"
            "animedia" -> "AniMedia"
            else -> providerCode
        }
}

/** #8: Full-week schedule. Loads all 7 days in parallel. */
class ScheduleViewModel(private val repo: AnimeRepository) : ViewModel() {

    private val _state = MutableStateFlow(ScheduleUiState())
    val state: StateFlow<ScheduleUiState> = _state.asStateFlow()

    companion object {
        private val SCHEDULE_INITIAL_SYNC_POLICIES = listOf(
            "animedia" to false,
        )

        private val SCHEDULE_SYNC_POLICIES = listOf(
            "aniliberty" to true,
            "animedia" to false,
        )

        private val DAY_NAMES = mapOf(
            1 to "Понедельник",
            2 to "Вторник",
            3 to "Среда",
            4 to "Четверг",
            5 to "Пятница",
            6 to "Суббота",
            7 to "Воскресенье",
        )
    }

    init {
        load(syncPolicies = SCHEDULE_INITIAL_SYNC_POLICIES)
    }

    fun refresh() = load(syncPolicies = SCHEDULE_SYNC_POLICIES, forceRefresh = true)

    fun loadProviderItem(
        item: ScheduleProviderItemState,
        onLoaded: (Int) -> Unit = {},
    ) {
        if (item.titleId != null) {
            onLoaded(item.titleId)
            return
        }

        viewModelScope.launch {
            val key = item.key
            _state.update {
                it.copy(
                    loadingProviderKeys = it.loadingProviderKeys + key,
                    actionMessage = null,
                )
            }
            runCatching {
                repo.fetchAndProcessTitle(
                    providerCode = item.providerCode,
                    externalId = item.fetchExternalId(),
                    mode = "title_full",
                )
            }.onSuccess { result ->
                _state.update {
                    it.copy(
                        loadingProviderKeys = it.loadingProviderKeys - key,
                        actionMessage = "Тайтл загружен",
                    )
                }
                result.titleId?.let(onLoaded)
                load(syncPolicies = SCHEDULE_INITIAL_SYNC_POLICIES)
            }.onFailure { e ->
                _state.update {
                    it.copy(
                        loadingProviderKeys = it.loadingProviderKeys - key,
                        actionMessage = "Ошибка загрузки тайтла: ${e.message ?: "unknown"}",
                    )
                }
            }
        }
    }

    private fun load(
        syncPolicies: List<Pair<String, Boolean>> = emptyList(),
        forceRefresh: Boolean = false,
    ) {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            runCatching {
                val providerItems = mutableListOf<ScheduleProviderItemState>()
                for ((providerCode, fetchUnresolved) in syncPolicies) {
                    val syncResult = repo.scheduleSync(
                        providerCode = providerCode,
                        fetchUnresolved = fetchUnresolved,
                        forceRefresh = forceRefresh,
                    )
                    if (providerCode == "animedia") {
                        val displayItems = syncResult.providerItems.ifEmpty { syncResult.unresolvedItems }
                        providerItems += displayItems.map { it.toProviderItemState() }
                    }
                }

                // Fetch all 7 days concurrently
                val jobs = (1..7).map { day ->
                    day to async { repo.getSchedule(day) }
                }
                val rawDays = jobs.map { (day, deferred) ->
                    val result = deferred.await()
                    ScheduleDayState(
                        day = day,
                        dayName = DAY_NAMES[day] ?: "День $day",
                        entries = result.entries,
                    )
                }
                val days = enrichTitleCards(rawDays)
                val providerSections = providerItems.toProviderSections()
                ScheduleUiState(
                    days = days.filter { it.entries.isNotEmpty() },
                    todayItems = providerSections.todayItems,
                    announcementItems = providerSections.announcementItems,
                    otherProviderItems = providerSections.otherProviderItems,
                    isLoading = false,
                )
            }.onSuccess { days ->
                _state.value = days
            }.onFailure { e ->
                _state.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }

    private suspend fun enrichTitleCards(days: List<ScheduleDayState>): List<ScheduleDayState> {
        val titleIds = days
            .flatMap { day -> day.entries.map { it.titleId } }
            .distinct()

        if (titleIds.isEmpty()) return days

        val titlesById = repo.getTitles(titleIds, view = "card")
            .associateBy { it.titleId }

        return days.map { day ->
            day.copy(
                entries = day.entries.map { entry ->
                    entry.copy(title = titlesById[entry.titleId])
                }
            )
        }
    }

    private data class ProviderSections(
        val todayItems: List<ScheduleProviderItemState>,
        val announcementItems: List<ScheduleProviderItemState>,
        val otherProviderItems: List<ScheduleProviderItemState>,
    )

    private fun ScheduleProviderItemDto.toProviderItemState(): ScheduleProviderItemState {
        val rawObj = raw as? JsonObject
        val rawTitle = rawObj?.get("title")?.jsonPrimitive?.contentOrNull
        val rawMeta = rawObj?.get("meta")?.jsonPrimitive?.contentOrNull
        val rawSection = rawObj?.get("section")?.jsonPrimitive?.contentOrNull
        return ScheduleProviderItemState(
            titleId = titleId,
            providerCode = providerCode,
            externalTitleId = externalTitleId,
            title = rawTitle?.takeIf { it.isNotBlank() } ?: externalTitleId,
            meta = rawMeta?.takeIf { it.isNotBlank() },
            episodeLabel = episodeLabel?.takeIf { it.isNotBlank() },
            posterUrl = posterUrl,
            titleUrl = titleUrl,
            dayOfWeek = dayOfWeek,
            airDt = airDt,
            section = rawSection,
        )
    }

    private fun List<ScheduleProviderItemState>.toProviderSections(): ProviderSections {
        val today = todayDatePrefix()
        val todayItems = filter { item ->
            item.airDt?.startsWith(today) == true ||
                item.meta?.contains("Сегодня", ignoreCase = true) == true ||
                item.meta?.contains("Новая серия", ignoreCase = true) == true
        }
        val todayKeys = todayItems.map { it.key }.toSet()

        val announcements = filter { item ->
            item.key !in todayKeys && item.section == "announcement"
        }
        val announcementKeys = announcements.map { it.key }.toSet()

        val other = filter { item ->
            item.key !in todayKeys && item.key !in announcementKeys
        }
        return ProviderSections(
            todayItems = todayItems,
            announcementItems = announcements,
            otherProviderItems = other,
        )
    }

    private fun todayDatePrefix(): String =
        Clock.System.now()
            .toLocalDateTime(TimeZone.currentSystemDefault())
            .date
            .toString()
}

private fun ScheduleProviderItemState.fetchExternalId(): String {
    val externalId = externalTitleId.trim()
    if (
        providerCode.equals("animedia", ignoreCase = true) &&
        "@@" !in externalId &&
        title.isNotBlank()
    ) {
        return "$externalId@@${title.trim()}"
    }
    return externalId
}
