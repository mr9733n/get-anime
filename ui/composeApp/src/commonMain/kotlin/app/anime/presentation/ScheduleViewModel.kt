package app.anime.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.anime.data.AnimeRepository
import app.anime.data.dto.ScheduleEntryDto
import app.anime.data.dto.TitleCardDto
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class ScheduleDayState(
    val day: Int,
    val dayName: String,
    val entries: List<ScheduleEntryDto> = emptyList(),
)

data class ScheduleUiState(
    val days: List<ScheduleDayState> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null,
)

/** #8: Full-week schedule. Loads all 7 days in parallel. */
class ScheduleViewModel(private val repo: AnimeRepository) : ViewModel() {

    private val _state = MutableStateFlow(ScheduleUiState())
    val state: StateFlow<ScheduleUiState> = _state.asStateFlow()

    companion object {
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
        load()
    }

    fun refresh() = load()

    private fun load() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            runCatching {
                // Fetch all 7 days concurrently
                val jobs = (1..7).map { day ->
                    day to async { repo.getSchedule(day) }
                }
                jobs.map { (day, deferred) ->
                    val result = deferred.await()
                    ScheduleDayState(
                        day = day,
                        dayName = DAY_NAMES[day] ?: "День $day",
                        entries = result.entries,
                    )
                }
            }.onSuccess { days ->
                _state.value = ScheduleUiState(
                    days = days.filter { it.entries.isNotEmpty() },
                    isLoading = false,
                )
            }.onFailure { e ->
                _state.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }
}
