package app.anime.data.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Full title — used on detail screen. */
@Serializable
data class TitleDetailsDto(
    @SerialName("title_id")      val titleId: Int,
    @SerialName("name_ru")       val nameRu: String? = null,
    @SerialName("name_en")       val nameEn: String? = null,
    @SerialName("description")   val description: String? = null,
    @SerialName("poster_url")    val posterUrl: String? = null,
    @SerialName("year")          val year: Int? = null,
    @SerialName("type")          val type: String? = null,
    @SerialName("status")        val status: String? = null,
    @SerialName("genres")        val genres: List<String> = emptyList(),
    @SerialName("episodes")      val episodes: List<EpisodeDto> = emptyList(),
    @SerialName("provider_links") val providerLinks: List<ProviderLinkDto> = emptyList(),
    // user prefs
    @SerialName("is_watched")    val isWatched: Boolean? = null,
    @SerialName("need_to_see")   val needToSee: Boolean? = null,
    @SerialName("history_records") val historyRecords: List<HistoryRecordDto> = emptyList(),
)

@Serializable
data class ProviderLinkDto(
    @SerialName("provider_code")       val providerCode: String,
    @SerialName("external_title_id")   val externalTitleId: String,
    @SerialName("provider_name")       val providerName: String? = null,
)

@Serializable
data class HistoryRecordDto(
    @SerialName("episode_id")    val episodeId: Int? = null,
    @SerialName("is_watched")    val isWatched: Boolean = false,
    @SerialName("watched_at")    val watchedAt: String? = null,
)

/** titles.get response envelope. */
@Serializable
data class TitlesGetResultDto(
    val titles: List<TitleDetailsDto>,
    val view: String,
)
