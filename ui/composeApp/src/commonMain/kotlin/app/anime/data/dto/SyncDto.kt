package app.anime.data.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class SyncFetchProcessEnvelopeDto(
    val result: SyncFetchProcessResultDto,
)

@Serializable
data class SyncFetchProcessResultDto(
    @SerialName("provider_code") val providerCode: String = "",
    val mode: String = "",
    @SerialName("external_id") val externalId: JsonElement? = null,
    @SerialName("title_id") val titleId: Int? = null,
    val ok: Boolean = false,
    val error: String? = null,
)

@Serializable
data class SyncSearchProcessEnvelopeDto(
    val result: SyncSearchProcessResultDto,
)

@Serializable
data class SyncSearchProcessResultDto(
    val ok: Boolean = false,
    @SerialName("provider_code") val providerCode: String = "",
    val query: String = "",
    val applied: List<SyncFetchProcessResultDto> = emptyList(),
    val skipped: Int = 0,
    val error: String? = null,
)
