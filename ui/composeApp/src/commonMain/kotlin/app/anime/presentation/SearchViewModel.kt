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

data class SearchUiState(
    val query: String = "",
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
) : ViewModel() {

    private val _state = MutableStateFlow(SearchUiState())
    val state: StateFlow<SearchUiState> = _state.asStateFlow()

    private var searchJob: Job? = null

    fun onQueryChange(query: String) {
        _state.update { it.copy(query = query) }
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(350) // debounce
            search(reset = true)
        }
    }

    fun loadMore() {
        if (_state.value.isLoading || !_state.value.hasMore) return
        viewModelScope.launch { search(reset = false) }
    }

    fun retry() {
        viewModelScope.launch { search(reset = true) }
    }

    private suspend fun search(reset: Boolean) {
        val q = _state.value.query.trim()
        val nextOffset = if (reset) 0 else _state.value.offset + pageSize

        _state.update { it.copy(isLoading = true, error = null) }

        runCatching {
            repo.searchTitles(query = q, limit = pageSize, offset = nextOffset, view = "card")
        }.onSuccess { dto ->
            _state.update { s ->
                val newResults = if (reset) dto.titles else s.results + dto.titles
                s.copy(
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
