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
    @SerialName("ratings")       val ratings: List<RatingDto> = emptyList(),
    @SerialName("franchises")    val franchises: List<FranchiseDto> = emptyList(),
    @SerialName("team_members")  val teamMembers: List<TeamMemberDto> = emptyList(),
    @SerialName("torrents")      val torrents: List<TorrentDto> = emptyList(),
    @SerialName("episodes")      val episodes: List<EpisodeDto> = emptyList(),
    @SerialName("provider_links") val providerLinks: List<ProviderLinkDto> = emptyList(),
    // user prefs
    @SerialName("is_watched")    val isWatched: Boolean? = null,
    @SerialName("all_episodes_watched") val allEpisodesWatched: Boolean? = null,
    @SerialName("watched_episode_count") val watchedEpisodeCount: Int? = null,
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

@Serializable
data class RatingDto(
    @SerialName("rating_name")   val ratingName: String? = null,
    @SerialName("rating_value")  val ratingValue: Int? = null,
    @SerialName("name_external") val nameExternal: String? = null,
    @SerialName("score_external") val scoreExternal: Double? = null,
)

@Serializable
data class FranchiseDto(
    @SerialName("franchise_id")  val franchiseId: Int? = null,
    @SerialName("franchise_name") val franchiseName: String? = null,
    @SerialName("code")          val code: String? = null,
    @SerialName("ordinal")       val ordinal: Int? = null,
    @SerialName("name_ru")       val nameRu: String? = null,
    @SerialName("name_en")       val nameEn: String? = null,
    @SerialName("name_alternative") val nameAlternative: String? = null,
    @SerialName("related_title_id") val relatedTitleId: Int? = null,
    @SerialName("related_title_name_ru") val relatedTitleNameRu: String? = null,
    @SerialName("related_title_name_en") val relatedTitleNameEn: String? = null,
)

@Serializable
data class TeamMemberDto(
    @SerialName("id")       val id: Int? = null,
    @SerialName("name")     val name: String,
    @SerialName("role")     val role: String,
)

@Serializable
data class TorrentDto(
    @SerialName("torrent_id")     val torrentId: Int,
    @SerialName("episodes_range") val episodesRange: String? = null,
    @SerialName("range_first")    val rangeFirst: Int? = null,
    @SerialName("range_last")     val rangeLast: Int? = null,
    @SerialName("quality")        val quality: String? = null,
    @SerialName("quality_type")   val qualityType: String? = null,
    @SerialName("resolution")     val resolution: String? = null,
    @SerialName("encoder")        val encoder: String? = null,
    @SerialName("leechers")       val leechers: Int? = null,
    @SerialName("seeders")        val seeders: Int? = null,
    @SerialName("downloads")      val downloads: Int? = null,
    @SerialName("total_size")     val totalSize: Long? = null,
    @SerialName("size_string")    val sizeString: String? = null,
    @SerialName("url")            val url: String? = null,
    @SerialName("magnet_link")    val magnetLink: String? = null,
    @SerialName("label")          val label: String? = null,
    @SerialName("filename")       val filename: String? = null,
    @SerialName("hash")           val hash: String? = null,
)

/** titles.get response envelope. */
@Serializable
data class TitlesGetResultDto(
    val titles: List<TitleDetailsDto>,
    val view: String,
)
