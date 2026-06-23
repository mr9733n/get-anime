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
    /** Play a direct media stream or playlist file via the configured video player. */
    data class Launch(
        val streamUrl: String,
        val episodeNumber: Int,
        val titleName: String,
        val titleId: Int,
        /** Raw JSON-encoded skip range, e.g. "[0.0, 89.5]". Null = no data. */
        val skipsOpening: String? = null,
        val skipsEnding: String? = null,
    ) : PlayerLaunchEvent
    /** Open a web-player page in a browser (URL is not a direct media stream). */
    data class OpenInBrowser(val url: String) : PlayerLaunchEvent
    data class Error(val message: String) : PlayerLaunchEvent
}

/** UI state for the "update from provider" action. */
sealed interface UpdateState {
    data object Idle    : UpdateState
    data object Loading : UpdateState
    data object Done    : UpdateState
    data class Error(val message: String) : UpdateState
}

class TitleViewModel(
    private val repo: AnimeRepository,
    private val titleId: Int,
) : ViewModel() {

    private val _uiState = MutableStateFlow<TitleDetailUiState>(TitleDetailUiState.Loading)
    val uiState: StateFlow<TitleDetailUiState> = _uiState.asStateFlow()

    private val _playerEvent = MutableSharedFlow<PlayerLaunchEvent>()
    val playerEvent: SharedFlow<PlayerLaunchEvent> = _playerEvent.asSharedFlow()

    private val _updateState = MutableStateFlow<UpdateState>(UpdateState.Idle)
    val updateState: StateFlow<UpdateState> = _updateState.asStateFlow()

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
                if (isWebPlayerUrl(url)) {
                    _playerEvent.emit(PlayerLaunchEvent.OpenInBrowser(url))
                } else {
                    _playerEvent.emit(PlayerLaunchEvent.Launch(
                        streamUrl = url,
                        episodeNumber = episode.episodeNumber,
                        titleName = titleName,
                        titleId = titleId,
                        skipsOpening = episode.skipsOpening,
                        skipsEnding = episode.skipsEnding,
                    ))
                }
            }.onFailure { e ->
                _playerEvent.emit(PlayerLaunchEvent.Error(e.message ?: "Stream error"))
            }
        }
    }

    /**
     * Compose a full-title playlist via the backend and send it to the video player.
     * The playlist file path is emitted as a [PlayerLaunchEvent.Launch] event —
     * mpv/vlc accept local .m3u8 paths directly.
     */
    fun playAll() {
        viewModelScope.launch {
            _updateState.value = UpdateState.Loading
            runCatching { repo.composeSinglePlaylist(titleId) }
                .onSuccess { path ->
                    _updateState.value = UpdateState.Idle
                    if (path.isNotEmpty()) {
                        val titleName = (_uiState.value as? TitleDetailUiState.Success)
                            ?.title?.nameRu ?: ""
                        _playerEvent.emit(PlayerLaunchEvent.Launch(path, 0, titleName, titleId))
                    }
                }
                .onFailure { e ->
                    _updateState.value = UpdateState.Error("Playlist: ${e.message}")
                }
        }
    }

    /**
     * Returns true when [url] is a web-player page rather than a direct media stream.
     * Such URLs should be opened in a browser, not passed to mpv/vlc.
     */
    private fun isWebPlayerUrl(url: String): Boolean {
        val lower = url.lowercase()
        if (!lower.startsWith("http://") && !lower.startsWith("https://")) return false
        // Direct media indicators — these go to the video player
        return !lower.contains(".m3u8") &&
            !lower.contains(".mp4") &&
            !lower.contains(".webm") &&
            !lower.contains(".mkv") &&
            !lower.contains(".avi") &&
            !(lower.endsWith(".ts") || lower.contains(".ts?")) &&
            !lower.contains("/hls/") &&
            !lower.contains("playlist")
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
            val watchedEpisodeCount = updatedEpisodes.count { it.isWatched == true }
            val allEpisodesWatched = updatedEpisodes.isNotEmpty() &&
                watchedEpisodeCount == updatedEpisodes.size
            val explicitTitleWatched = current.title.historyRecords.any {
                it.episodeId == null && it.isWatched
            }
            _uiState.value = TitleDetailUiState.Success(
                current.title.copy(
                    episodes = updatedEpisodes,
                    watchedEpisodeCount = watchedEpisodeCount,
                    allEpisodesWatched = allEpisodesWatched,
                    isWatched = explicitTitleWatched || allEpisodesWatched,
                )
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
                current.title.copy(
                    episodes = updatedEpisodes,
                    watchedEpisodeCount = if (watched) updatedEpisodes.size else 0,
                    allEpisodesWatched = watched && updatedEpisodes.isNotEmpty(),
                    isWatched = watched,
                )
            )
        }
    }

    /** #3: Re-fetch title data from its upstream provider(s) and reload. */
    fun updateFromProvider(forceRefresh: Boolean = false) {
        viewModelScope.launch {
            _updateState.value = UpdateState.Loading
            runCatching {
                repo.updateTitle(
                    titleId = titleId,
                    providerCode = if (forceRefresh) "animedia" else null,
                    forceRefresh = forceRefresh,
                )
            }
                .onSuccess {
                    _updateState.value = UpdateState.Done
                    // Reload to show updated data
                    loadTitle()
                }
                .onFailure { e ->
                    _updateState.value = UpdateState.Error(e.message ?: "Update failed")
                }
        }
    }

    fun dismissUpdateResult() {
        _updateState.value = UpdateState.Idle
    }
}
