package app.anime.data.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ScheduleEntryDto(
    @SerialName("title_id")       val titleId: Int,
    @SerialName("day_of_week")    val dayOfWeek: Int,          // 1=Mon…7=Sun
    @SerialName("last_updated")   val lastUpdated: String? = null,
    // enriched with title card data when fetched via titles.get
    val title: TitleCardDto? = null,
)

@Serializable
data class ScheduleGetResultDto(
    val day: Int,
    val entries: List<ScheduleEntryDto>,
)
