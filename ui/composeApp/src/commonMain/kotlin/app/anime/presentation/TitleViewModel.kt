package app.anime.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.anime.data.AnimeRepository
import app.anime.data.dto.EpisodeDto
import app.anime.data.dto.TitleDetailsDto
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

sealed interface TitleDetailUiState {
    data object Loading : TitleDetailUiState
    data class Success(val title: TitleDetailsDto) : TitleDetailUiState
    data class Error(val message: String) : TitleDetailUiState
}

sealed interface PlayerLaunchEvent {
    data class Launch(val streamUrl: String, val episodeNumber: Int, val titleName: String) : PlayerLaunchEvent
    data class Error(val message: String) : PlayerLaunchEvent
}

class TitleViewModel(
    private val repo: AnimeRepository,
    private val titleId: Int,
) : ViewModel() {

    private val _uiState = MutableStateFlow<TitleDetailUiState>(TitleDetailUiState.Loading)
    val uiState: StateFlow<TitleDetailUiState> = _uiState.asStateFlow()

    private val _playerEvent = MutableSharedFlow<PlayerLaunchEvent>()
    val playerEvent: SharedFlow<PlayerLaunchEvent> = _playerEvent.asSharedFlow()

    init {
        loadTitle()
    }

    private fun loadTitle() {
        viewModelScope.launch {
            _uiState.value = TitleDetailUiState.Loading
            runCatching { repo.getTitle(titleId) }
                .onSuccess { _uiState.value = TitleDetailUiState.Success(it) }
                .onFailure { _uiState.value = TitleDetailUiState.Error(it.message ?: "Error") }
        }
    }

    fun onEpisodeClick(episode: EpisodeDto) {
        viewModelScope.launch {
            runCatching {
                repo.getStream(
                    titleId = episode.titleId,
                    episodeNumber = episode.episodeNumber,
                )
            }.onSuccess { stream ->
                val url = stream.bestUrl ?: stream.urlHd ?: stream.urlSd
                ?: throw Exception("No stream URL available")
                val titleName = (_uiState.value as? TitleDetailUiState.Success)
                    ?.title?.nameRu ?: "Episode ${episode.episodeNumber}"
                _playerEvent.emit(PlayerLaunchEvent.Launch(url, episode.episodeNumber, titleName))
            }.onFailure { e ->
                _playerEvent.emit(PlayerLaunchEvent.Error(e.message ?: "Stream error"))
            }
        }
    }

    fun markEpisodeWatched(episode: EpisodeDto, watched: Boolean = true) {
        viewModelScope.launch {
            runCatching {
                repo.markWatched(
                    titleId = episode.titleId,
                    episodeId = episode.episodeId,
                    isWatched = watched,
                )
            }
            // Optimistic update
            val current = (_uiState.value as? TitleDetailUiState.Success) ?: return@launch
            val updatedEpisodes = current.title.episodes.map {
                if (it.episodeId == episode.episodeId) it.copy(isWatched = watched) else it
            }
            _uiState.value = TitleDetailUiState.Success(
                current.title.copy(episodes = updatedEpisodes)
            )
        }
    }

    fun toggleNeedToSee() {
        val current = (_uiState.value as? TitleDetailUiState.Success) ?: return
        val newValue = !(current.title.needToSee ?: false)
        viewModelScope.launch {
            runCatching { repo.setNeedToSee(titleId, newValue) }
            _uiState.value = TitleDetailUiState.Success(
                current.title.copy(needToSee = newValue)
            )
        }
    }

    fun markAllWatched(watched: Boolean = true) {
        viewModelScope.launch {
            runCatching { repo.markAllWatched(titleId, watched) }
            val current = (_uiState.value as? TitleDetailUiState.Success) ?: return@launch
            val updatedEpisodes = current.title.episodes.map { it.copy(isWatched = watched) }
            _uiState.value = TitleDetailUiState.Success(
                current.title.copy(episodes = updatedEpisodes)
            )
        }
    }
}
