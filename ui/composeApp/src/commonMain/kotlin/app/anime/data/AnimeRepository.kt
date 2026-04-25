package app.anime.data

import app.anime.data.dto.*
import kotlinx.serialization.json.*

/**
 * Single repository wrapping all backend calls.
 * ViewModels depend on this, not on BackendClient directly.
 */
class AnimeRepository(private val client: BackendClient) {

    private val json = Json { ignoreUnknownKeys = true }

    // -----------------------------------------------------------------------
    // Titles
    // -----------------------------------------------------------------------

    suspend fun searchTitles(
        query: String,
        limit: Int = 50,
        offset: Int = 0,
        view: String = "card",
    ): TitlesSearchResultDto {
        val result = client.call(
            "titles.search", mapOf(
                "query" to query,
                "limit" to limit,
                "offset" to offset,
                "view" to view,
            )
        )
        return json.decodeFromJsonElement(result)
    }

    suspend fun getTitle(titleId: Int, view: String = "full"): TitleDetailsDto {
        val result = client.call(
            "titles.get", mapOf("title_id" to titleId, "view" to view)
        )
        val dto: TitlesGetResultDto = json.decodeFromJsonElement(result)
        return dto.titles.first()
    }

    suspend fun getTitles(
        titleIds: List<Int>,
        view: String = "card",
    ): List<TitleCardDto> {
        val result = client.call(
            "titles.get", mapOf("title_ids" to titleIds, "view" to view)
        )
        // When view=card the result titles are TitleCardDto-compatible
        return result["titles"]
            ?.jsonArray
            ?.map { json.decodeFromJsonElement<TitleCardDto>(it) }
            ?: emptyList()
    }

    suspend fun listEpisodes(titleId: Int): List<EpisodeDto> {
        val result = client.call(
            "titles.list_episodes", mapOf("title_id" to titleId)
        )
        return result["episodes"]
            ?.jsonArray
            ?.map { json.decodeFromJsonElement(it) }
            ?: emptyList()
    }

    // -----------------------------------------------------------------------
    // Streams
    // -----------------------------------------------------------------------

    suspend fun getStream(titleId: Int, episodeNumber: Int): StreamDto {
        val result = client.call(
            "streams.get", mapOf("title_id" to titleId, "episode_number" to episodeNumber)
        )
        val dto: StreamResultDto = json.decodeFromJsonElement(result)
        return dto.stream
    }

    // -----------------------------------------------------------------------
    // Schedule
    // -----------------------------------------------------------------------

    suspend fun getSchedule(day: Int): ScheduleGetResultDto {
        val result = client.call("schedule.get", mapOf("day" to day))
        return json.decodeFromJsonElement(result)
    }

    // -----------------------------------------------------------------------
    // History (write)
    // -----------------------------------------------------------------------

    suspend fun markWatched(
        titleId: Int,
        episodeId: Int? = null,
        isWatched: Boolean = true,
        userId: Int = 42,
    ) {
        client.call(
            "history.mark_watched", mapOf(
                "title_id" to titleId,
                "episode_id" to episodeId,
                "is_watched" to isWatched,
                "user_id" to userId,
            )
        )
    }

    suspend fun markAllWatched(
        titleId: Int,
        isWatched: Boolean = true,
        episodeIds: List<Int>? = null,
    ) {
        client.call(
            "history.mark_all_watched", mapOf(
                "title_id" to titleId,
                "is_watched" to isWatched,
                "episode_ids" to episodeIds,
            )
        )
    }

    suspend fun setNeedToSee(titleId: Int, needToSee: Boolean) {
        client.call(
            "history.set_need_to_see", mapOf(
                "title_id" to titleId,
                "need_to_see" to needToSee,
            )
        )
    }

    // -----------------------------------------------------------------------
    // Playlist
    // -----------------------------------------------------------------------

    suspend fun composeSinglePlaylist(titleId: Int, quality: String = "best"): String {
        val result = client.call(
            "playlist.compose", mapOf("title_id" to titleId, "quality" to quality)
        )
        return result["path"]?.jsonPrimitive?.content ?: ""
    }

    fun close() = client.close()
}
