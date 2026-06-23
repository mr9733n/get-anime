package app.anime.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.anime.data.AnimeRepository
import app.anime.data.dto.ScheduleEntryDto
import app.anime.data.dto.TitleCardDto
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.datetime.*

data class HomeUiState(
    val todaySchedule: List<ScheduleEntryDto> = emptyList(),
    val tomorrowSchedule: List<ScheduleEntryDto> = emptyList(),
    val watchlist: List<TitleCardDto> = emptyList(),
    val recent: List<TitleCardDto> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null,
)

class HomeViewModel(private val repo: AnimeRepository) : ViewModel() {

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun refresh() {
        load()
    }

    private fun load() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }

            runCatching {
                val today = Clock.System.now()
                    .toLocalDateTime(TimeZone.currentSystemDefault())
                    .dayOfWeek.isoDayNumber          // 1=Mon…7=Sun
                val tomorrow = if (today == 7) 1 else today + 1

                val todayJob = async { repo.getSchedule(today) }
                val tomorrowJob = async { repo.getSchedule(tomorrow) }

                todayJob.await() to tomorrowJob.await()
            }.onSuccess { (today, tomorrow) ->
                _state.update {
                    it.copy(
                        todaySchedule = today.entries,
                        tomorrowSchedule = tomorrow.entries,
                        isLoading = false,
                    )
                }
            }.onFailure { e ->
                _state.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }
}
