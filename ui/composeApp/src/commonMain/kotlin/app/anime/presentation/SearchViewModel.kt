package app.anime.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.anime.data.AnimeRepository
import app.anime.data.dto.TitleCardDto
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class SearchFilters(
    val year: Int? = null,
    val genre: String = "",
    val status: String = "",
    val type: String = "",
    val teamMemberId: Int? = null,
    val teamMember: String = "",
    val franchiseId: Int? = null,
    val franchise: String = "",
) {
    val isActive: Boolean
        get() = year != null ||
            genre.isNotBlank() ||
            status.isNotBlank() ||
            type.isNotBlank() ||
            teamMemberId != null ||
            teamMember.isNotBlank() ||
            franchiseId != null ||
            franchise.isNotBlank()
}

data class SearchUiState(
    val query: String = "",
    val filters: SearchFilters = SearchFilters(),
    val facetTitle: String? = null,
    val showFilters: Boolean = false,
    val results: List<TitleCardDto> = emptyList(),
    val watchlist: List<TitleCardDto> = emptyList(),
    val recentTitles: List<TitleCardDto> = emptyList(),
    val isLoading: Boolean = false,
    val hasMore: Boolean = false,
    val totalCount: Int = 0,
    val offset: Int = 0,
    val error: String? = null,
    val providerLoadInProgress: String? = null,
    val providerLoadError: String? = null,
    val randomLoadInProgress: Boolean = false,
    val randomLoadError: String? = null,
)

class SearchViewModel(
    private val repo: AnimeRepository,
    private val pageSize: Int = 50,
    initialQuery: String = "",
    initialFilters: SearchFilters = SearchFilters(),
    initialFacetTitle: String? = null,
    /** When true, automatically load all titles on first open (Browse / Catalog mode). */
    autoLoad: Boolean = false,
) : ViewModel() {

    private val _state = MutableStateFlow(
        SearchUiState(
            query = initialQuery,
            filters = initialFilters,
            showFilters = initialFilters.isActive,
            facetTitle = initialFacetTitle,
        )
    )
    val state: StateFlow<SearchUiState> = _state.asStateFlow()

    private var searchJob: Job? = null

    init {
        if (autoLoad) {
            viewModelScope.launch { search(reset = true) }
            viewModelScope.launch { loadHomeRails() }
        }
    }

    fun onQueryChange(query: String) {
        _state.update { it.copy(query = query) }
        debounceSearch()
    }

    /** #9: Update a filter and restart search. */
    fun onFilterChange(filters: SearchFilters) {
        _state.update { cur ->
            cur.copy(filters = filters, facetTitle = cur.facetTitle?.takeIf { filters.isActive })
        }
        debounceSearch()
    }

    fun toggleFiltersPanel() {
        _state.update { it.copy(showFilters = !it.showFilters) }
    }

    fun loadMore() {
        if (_state.value.isLoading || !_state.value.hasMore) return
        viewModelScope.launch { search(reset = false) }
    }

    fun retry() {
        viewModelScope.launch {
            search(reset = true)
            loadHomeRails()
        }
    }

    fun loadFromProvider(
        providerCode: String,
        providerQuery: String = _state.value.query,
        byExternalId: Boolean = false,
        limit: Int = 1,
        onLoaded: (Int) -> Unit,
    ) {
        val q = providerQuery.trim()
        if (q.isBlank() || _state.value.providerLoadInProgress != null) return

        viewModelScope.launch {
            _state.update {
                it.copy(
                    providerLoadInProgress = providerCode,
                    providerLoadError = null,
                )
            }

            runCatching {
                if (byExternalId) {
                    val result = repo.fetchAndProcessTitle(
                        providerCode = providerCode,
                        externalId = q,
                        mode = "title_full",
                    )
                    listOf(result)
                } else {
                    repo.searchAndProcessTitle(
                        providerCode = providerCode,
                        query = q,
                        mode = "title_full",
                        maxResults = maxOf(5, limit),
                        limit = limit.coerceIn(1, 5),
                    ).applied
                }
            }.onSuccess { result ->
                val loadedTitleId = result.firstOrNull { it.ok && it.titleId != null }?.titleId
                if (loadedTitleId != null) {
                    _state.update {
                        it.copy(
                            providerLoadInProgress = null,
                            providerLoadError = null,
                        )
                    }
                    onLoaded(loadedTitleId)
                } else {
                    _state.update {
                        it.copy(
                            providerLoadInProgress = null,
                            providerLoadError = result.firstOrNull { !it.error.isNullOrBlank() }?.error
                                ?: providerLoadEmptyMessage(providerCode),
                        )
                    }
                }
            }.onFailure { e ->
                _state.update {
                    it.copy(
                        providerLoadInProgress = null,
                        providerLoadError = e.message ?: providerLoadEmptyMessage(providerCode),
                    )
                }
            }
        }
    }

    fun loadRandomAniLiberty(onLoaded: (Int) -> Unit) {
        if (_state.value.randomLoadInProgress) return

        viewModelScope.launch {
            _state.update {
                it.copy(
                    randomLoadInProgress = true,
                    randomLoadError = null,
                    providerLoadError = null,
                )
            }

            runCatching {
                repo.randomAndProcessTitle(providerCode = "aniliberty", mode = "title_full")
            }.onSuccess { result ->
                val loadedTitleId = result.titleId
                if (loadedTitleId != null) {
                    _state.update {
                        it.copy(
                            randomLoadInProgress = false,
                            randomLoadError = null,
                        )
                    }
                    onLoaded(loadedTitleId)
                } else {
                    _state.update {
                        it.copy(
                            randomLoadInProgress = false,
                            randomLoadError = result.error ?: "\u0421\u043b\u0443\u0447\u0430\u0439\u043d\u044b\u0439 \u0442\u0430\u0439\u0442\u043b \u043d\u0435 \u0431\u044b\u043b \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d",
                        )
                    }
                }
            }.onFailure { e ->
                _state.update {
                    it.copy(
                        randomLoadInProgress = false,
                        randomLoadError = e.message ?: "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0441\u043b\u0443\u0447\u0430\u0439\u043d\u044b\u0439 \u0442\u0430\u0439\u0442\u043b",
                    )
                }
            }
        }
    }

    private fun debounceSearch() {
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(350) // debounce
            search(reset = true)
        }
    }

    private suspend fun search(reset: Boolean) {
        val s = _state.value
        val q = s.query.trim()
        val f = s.filters
        val nextOffset = if (reset) 0 else s.offset + pageSize

        _state.update { it.copy(isLoading = true, error = null, providerLoadError = null, randomLoadError = null) }

        runCatching {
            repo.searchTitles(
                query = q,
                limit = pageSize,
                offset = nextOffset,
                view = "card",
                year = f.year,
                genre = f.genre.ifBlank { null },
                statusFilter = f.status.ifBlank { null },
                typeFilter = f.type.ifBlank { null },
                teamMemberId = f.teamMemberId,
                teamMember = f.teamMember.ifBlank { null },
                franchiseId = f.franchiseId,
            )
        }.onSuccess { dto ->
            _state.update { cur ->
                val newResults = if (reset) dto.titles else cur.results + dto.titles
                cur.copy(
                    results = newResults,
                    isLoading = false,
                    hasMore = dto.hasMore,
                    totalCount = dto.totalCount,
                    offset = nextOffset,
                )
            }
        }.onFailure { e ->
            _state.update { it.copy(isLoading = false, error = e.message) }
        }
    }

    private suspend fun loadWatchlist() {
        runCatching {
            repo.searchTitles(
                query = "",
                limit = 12,
                offset = 0,
                view = "card",
                needToSee = true,
            )
        }.onSuccess { dto ->
            _state.update { it.copy(watchlist = dto.titles) }
        }
    }

    private suspend fun loadRecentTitles() {
        runCatching {
            repo.searchTitles(
                query = "",
                limit = 12,
                offset = 0,
                view = "card",
                sort = "recent",
            )
        }.onSuccess { dto ->
            _state.update { it.copy(recentTitles = dto.titles) }
        }
    }

    private suspend fun loadHomeRails() {
        loadRecentTitles()
        loadWatchlist()
    }

    private fun providerLoadEmptyMessage(providerCode: String): String =
        "\u041f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440 ${providerCode.ifBlank { "unknown" }} \u043d\u0435 \u0432\u0435\u0440\u043d\u0443\u043b \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u043d\u044b\u0439 \u0442\u0430\u0439\u0442\u043b"
}
