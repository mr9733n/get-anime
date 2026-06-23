package app.anime.data.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

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

@Serializable
data class ScheduleSyncEnvelopeDto(
    val result: ScheduleSyncResultDto,
)

@Serializable
data class ScheduleSyncResultDto(
    val ok: Boolean = true,
    @SerialName("provider_code") val providerCode: String = "",
    val fetched: Int = 0,
    val upserted: Int = 0,
    val unresolved: Int = 0,
    @SerialName("fetched_missing") val fetchedMissing: Int = 0,
    val error: String? = null,
    @SerialName("provider_items") val providerItems: List<ScheduleProviderItemDto> = emptyList(),
    @SerialName("unresolved_items") val unresolvedItems: List<ScheduleProviderItemDto> = emptyList(),
)

@Serializable
data class ScheduleProviderItemDto(
    @SerialName("title_id") val titleId: Int? = null,
    @SerialName("provider_code") val providerCode: String,
    @SerialName("external_title_id") val externalTitleId: String,
    @SerialName("day_of_week") val dayOfWeek: Int? = null,
    @SerialName("air_dt") val airDt: String? = null,
    @SerialName("episode_label") val episodeLabel: String? = null,
    @SerialName("poster_url") val posterUrl: String? = null,
    @SerialName("title_url") val titleUrl: String? = null,
    val raw: JsonElement? = null,
)
