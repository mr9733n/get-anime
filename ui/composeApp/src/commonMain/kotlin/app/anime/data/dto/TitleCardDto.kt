package app.anime.data.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Lightweight title — used in search results, schedule, home rows. */
@Serializable
data class TitleCardDto(
    @SerialName("title_id")    val titleId: Int,
    @SerialName("name_ru")     val nameRu: String? = null,
    @SerialName("name_en")     val nameEn: String? = null,
    @SerialName("poster_url")  val posterUrl: String? = null,
    @SerialName("year")        val year: Int? = null,
    @SerialName("type")        val type: String? = null,
    @SerialName("status")      val status: String? = null,
    @SerialName("day_of_week") val dayOfWeek: Int? = null,
    @SerialName("day_name")    val dayName: String? = null,
    @SerialName("episodes_count") val episodesCount: Int? = null,
    @SerialName("provider")    val provider: String? = null,
    @SerialName("genres")      val genres: List<String> = emptyList(),
    @SerialName("rating_name")  val ratingName: String? = null,
    @SerialName("rating_value") val ratingValue: Int? = null,
    @SerialName("ratings")      val ratings: List<RatingDto> = emptyList(),
    // user prefs (available when enrich=true)
    @SerialName("is_watched")     val isWatched: Boolean? = null,
    @SerialName("all_episodes_watched") val allEpisodesWatched: Boolean? = null,
    @SerialName("need_to_see")    val needToSee: Boolean? = null,
)

/** Search response envelope. */
@Serializable
data class TitlesSearchResultDto(
    val titles: List<TitleCardDto>,
    val view: String,
    @SerialName("total_count") val totalCount: Int,
    val offset: Int,
    val limit: Int,
    @SerialName("has_more")   val hasMore: Boolean,
)
