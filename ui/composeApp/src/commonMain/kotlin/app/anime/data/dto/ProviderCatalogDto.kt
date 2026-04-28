package app.anime.data.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ProviderCatalogEnvelopeDto(
    val result: ProviderCatalogResultDto,
)

@Serializable
data class ProviderCatalogResultDto(
    val ok: Boolean = true,
    @SerialName("provider_code") val providerCode: String = "",
    val fetched: Int = 0,
    val items: List<ScheduleProviderItemDto> = emptyList(),
    val error: String? = null,
)
