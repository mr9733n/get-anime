package app.anime.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.anime.data.AnimeRepository
import app.anime.data.dto.ScheduleProviderItemDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive

data class AniMediaCatalogUiState(
    val items: List<ScheduleProviderItemState> = emptyList(),
    val query: String = "",
    val showLoadedOnly: Boolean? = null,
    val loadingProviderKeys: Set<String> = emptySet(),
    val actionMessage: String? = null,
    val isLoading: Boolean = true,
    val isLoadingMore: Boolean = false,
    val error: String? = null,
)

class AniMediaCatalogViewModel(private val repo: AnimeRepository) : ViewModel() {
    private val _state = MutableStateFlow(AniMediaCatalogUiState())
    val state: StateFlow<AniMediaCatalogUiState> = _state.asStateFlow()

    init {
        load(loadMore = false)
    }

    fun onQueryChange(query: String) {
        _state.update { it.copy(query = query) }
    }

    fun onLoadedFilterChange(value: Boolean?) {
        _state.update { it.copy(showLoadedOnly = value) }
    }

    fun refresh() = load(loadMore = false)

    fun loadMore() = load(loadMore = true)

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
                refresh()
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

    private fun load(loadMore: Boolean) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    isLoading = !loadMore,
                    isLoadingMore = loadMore,
                    error = null,
                    actionMessage = null,
                )
            }
            runCatching {
                repo.providerCatalog(
                    providerCode = "animedia",
                    maxTitles = 180,
                    pages = 5,
                    loadMore = loadMore,
                ).items.map { it.toProviderItemState() }
            }.onSuccess { items ->
                _state.update {
                    it.copy(
                        items = items,
                        isLoading = false,
                        isLoadingMore = false,
                    )
                }
            }.onFailure { e ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        isLoadingMore = false,
                        error = e.message,
                    )
                }
            }
        }
    }

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
