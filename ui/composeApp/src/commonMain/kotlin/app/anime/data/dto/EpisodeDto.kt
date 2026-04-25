package app.anime.data.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class EpisodeDto(
    @SerialName("episode_id")      val episodeId: Int,
    @SerialName("episode_number")  val episodeNumber: Int,
    @SerialName("title")           val title: String? = null,
    @SerialName("title_id")        val titleId: Int,
    @SerialName("hls_sd")          val hlsSd: String? = null,
    @SerialName("hls_hd")          val hlsHd: String? = null,
    @SerialName("hls_fhd")         val hlsFhd: String? = null,
    @SerialName("preview_abs")     val previewAbs: String? = null,
    // per-episode user prefs (from enricher)
    @SerialName("is_watched")      val isWatched: Boolean? = null,
)

@Serializable
data class StreamDto(
    @SerialName("title_id")        val titleId: Int,
    @SerialName("episode_id")      val episodeId: Int,
    @SerialName("episode_number")  val episodeNumber: Int,
    @SerialName("url_sd")          val urlSd: String? = null,
    @SerialName("url_hd")          val urlHd: String? = null,
    @SerialName("url_fhd")         val urlFhd: String? = null,
    @SerialName("best_url")        val bestUrl: String? = null,
    @SerialName("best_quality")    val bestQuality: String? = null,
)

@Serializable
data class StreamResultDto(
    val stream: StreamDto,
)
