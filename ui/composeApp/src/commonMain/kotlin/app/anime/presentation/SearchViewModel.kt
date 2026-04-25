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
) {
    val isActive: Boolean
        get() = year != null || genre.isNotBlank() || status.isNotBlank() || type.isNotBlank()
}

data class SearchUiState(
    val query: String = "",
    val filters: SearchFilters = SearchFilters(),
    val showFilters: Boolean = false,
    val results: List<TitleCardDto> = emptyList(),
    val isLoading: Boolean = false,
    val hasMore: Boolean = false,
    val totalCount: Int = 0,
    val offset: Int = 0,
    val error: String? = null,
)

class SearchViewModel(
    private val repo: AnimeRepository,
    private val pageSize: Int = 50,
    /** When true, automatically load all titles on first open (Browse / Catalog mode). */
    autoLoad: Boolean = false,
) : ViewModel() {

    private val _state = MutableStateFlow(SearchUiState())
    val state: StateFlow<SearchUiState> = _state.asStateFlow()

    private var searchJob: Job? = null

    init {
        if (autoLoad) {
            viewModelScope.launch { search(reset = true) }
        }
    }

    fun onQueryChange(query: String) {
        _state.update { it.copy(query = query) }
        debounceSearch()
    }

    /** #9: Update a filter and restart search. */
    fun onFilterChange(filters: SearchFilters) {
        _state.update { it.copy(filters = filters) }
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
        viewModelScope.launch { search(reset = true) }
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

        _state.update { it.copy(isLoading = true, error = null) }

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
}
