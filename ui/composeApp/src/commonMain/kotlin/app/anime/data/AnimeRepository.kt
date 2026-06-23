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
    // URL helpers
    // -----------------------------------------------------------------------

    /**
     * Resolve a URL from the backend:
     * - Absolute URLs (http/https) → returned as-is.
     * - Relative paths starting with "/" → prefixed with [client.baseUrl].
     * - null → null.
     *
     * The backend returns "/poster/<id>" when no CDN URL is stored; the client
     * turns that into a full URL using the known backend address.
     */
    fun resolveUrl(url: String?): String? = when {
        url == null -> null
        url.startsWith("http://") || url.startsWith("https://") -> url
        url.startsWith("/") -> client.baseUrl.trimEnd('/') + url
        else -> url
    }

    /** Direct poster URL for a title (backend /poster endpoint). */
    fun posterUrl(titleId: Int): String = "${client.baseUrl.trimEnd('/')}/poster/$titleId"

    // -----------------------------------------------------------------------
    // Titles
    // -----------------------------------------------------------------------

    suspend fun searchTitles(
        query: String,
        limit: Int = 50,
        offset: Int = 0,
        view: String = "card",
        // #9 filters
        year: Int? = null,
        genre: String? = null,
        statusFilter: String? = null,
        typeFilter: String? = null,
        needToSee: Boolean? = null,
        teamMemberId: Int? = null,
        teamMember: String? = null,
        franchiseId: Int? = null,
        sort: String? = null,
    ): TitlesSearchResultDto {
        val params = buildMap<String, Any?> {
            put("query", query)
            put("limit", limit)
            put("offset", offset)
            put("view", view)
            if (year != null) put("year", year)
            if (!genre.isNullOrBlank()) put("genre", genre)
            if (!statusFilter.isNullOrBlank()) put("status_filter", statusFilter)
            if (!typeFilter.isNullOrBlank()) put("type_filter", typeFilter)
            if (needToSee == true) put("need_to_see", true)
            if (teamMemberId != null) put("team_member_id", teamMemberId)
            if (!teamMember.isNullOrBlank()) put("team_member", teamMember)
            if (franchiseId != null) put("franchise_id", franchiseId)
            if (!sort.isNullOrBlank()) put("sort", sort)
        }
        val result = client.call("titles.search", params)
        val dto: TitlesSearchResultDto = json.decodeFromJsonElement(result)
        // Resolve relative poster URLs (e.g. /poster/42 → http://host/poster/42)
        return dto.copy(titles = dto.titles.map { it.copy(posterUrl = resolveUrl(it.posterUrl)) })
    }

    suspend fun getTitle(titleId: Int, view: String = "full"): TitleDetailsDto {
        val result = client.call(
            "titles.get", mapOf("title_id" to titleId, "view" to view)
        )
        val dto: TitlesGetResultDto = json.decodeFromJsonElement(result)
        val t = dto.titles.first()
        return t.copy(posterUrl = resolveUrl(t.posterUrl))
    }

    suspend fun getTitles(
        titleIds: List<Int>,
        view: String = "card",
    ): List<TitleCardDto> {
        val result = client.call(
            "titles.get", mapOf("title_ids" to titleIds, "view" to view)
        )
        return result["titles"]
            ?.jsonArray
            ?.map {
                val t: TitleCardDto = json.decodeFromJsonElement(it)
                t.copy(posterUrl = resolveUrl(t.posterUrl))
            }
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

    suspend fun scheduleSync(
        providerCode: String,
        day: Int? = null,
        fetchUnresolved: Boolean = false,
        forceRefresh: Boolean = false,
    ): ScheduleSyncResultDto {
        val params = buildMap<String, Any?> {
            put("provider_code", providerCode)
            put("fetch_unresolved", fetchUnresolved)
            put("force_refresh", forceRefresh)
            if (day != null) put("day", day)
        }
        val result = client.call("schedule.sync", params)
        val envelope: ScheduleSyncEnvelopeDto = json.decodeFromJsonElement(result)
        val syncResult = envelope.result.copy(
            providerItems = envelope.result.providerItems.map { item ->
                item.copy(posterUrl = resolveUrl(item.posterUrl))
            },
            unresolvedItems = envelope.result.unresolvedItems.map { item ->
                item.copy(posterUrl = resolveUrl(item.posterUrl))
            }
        )
        val ok = syncResult.ok
        if (!ok) {
            val error = syncResult.error
            throw BackendException(error ?: "Schedule sync failed for provider '$providerCode'", "schedule.sync")
        }
        return syncResult
    }

    suspend fun fetchAndProcessTitle(
        providerCode: String,
        externalId: String,
        mode: String = "title_full",
    ): SyncFetchProcessResultDto {
        val result = client.call(
            "sync.fetch_and_process",
            mapOf(
                "provider_code" to providerCode,
                "external_id" to externalId,
                "mode" to mode,
            ),
        )
        val envelope: SyncFetchProcessEnvelopeDto = json.decodeFromJsonElement(result)
        val syncResult = envelope.result
        if (!syncResult.ok) {
            throw BackendException(
                syncResult.error ?: "Title load failed for provider '$providerCode'",
                "sync.fetch_and_process",
            )
        }
        return syncResult
    }

    suspend fun providerCatalog(
        providerCode: String,
        maxTitles: Int = 120,
        pages: Int = 5,
        loadMore: Boolean = false,
    ): ProviderCatalogResultDto {
        val result = client.call(
            "provider.catalog",
            mapOf(
                "provider_code" to providerCode,
                "max_titles" to maxTitles,
                "pages" to pages,
                "load_more" to loadMore,
            ),
        )
        val envelope: ProviderCatalogEnvelopeDto = json.decodeFromJsonElement(result)
        val catalog = envelope.result.copy(
            items = envelope.result.items.map { item ->
                item.copy(posterUrl = resolveUrl(item.posterUrl))
            }
        )
        if (!catalog.ok) {
            throw BackendException(
                catalog.error ?: "Provider catalog failed for '$providerCode'",
                "provider.catalog",
            )
        }
        return catalog
    }

    suspend fun searchAndProcessTitle(
        providerCode: String,
        query: String,
        mode: String = "title_full",
        maxResults: Int = 5,
        limit: Int = 1,
    ): SyncSearchProcessResultDto {
        val result = client.call(
            "sync.search_and_process",
            mapOf(
                "provider_code" to providerCode,
                "query" to query,
                "mode" to mode,
                "max_results" to maxResults,
                "limit" to limit,
            ),
        )
        val envelope: SyncSearchProcessEnvelopeDto = json.decodeFromJsonElement(result)
        val syncResult = envelope.result
        if (!syncResult.ok) {
            throw BackendException(
                syncResult.error ?: "Title search/load failed for provider '$providerCode'",
                "sync.search_and_process",
            )
        }
        return syncResult
    }

    suspend fun randomAndProcessTitle(
        providerCode: String = "aniliberty",
        mode: String = "title_full",
    ): SyncFetchProcessResultDto {
        val result = client.call(
            "sync.random_and_process",
            mapOf(
                "provider_code" to providerCode,
                "mode" to mode,
            ),
        )
        val envelope: SyncFetchProcessEnvelopeDto = json.decodeFromJsonElement(result)
        val syncResult = envelope.result
        if (!syncResult.ok) {
            throw BackendException(
                syncResult.error ?: "Random title load failed for provider '$providerCode'",
                "sync.random_and_process",
            )
        }
        return syncResult
    }

    // -----------------------------------------------------------------------
    // Sync / Update (#3)
    // -----------------------------------------------------------------------

    /**
     * Trigger a backend title update from its provider(s).
     * Maps to the `titles.update` JSON-tool op.
     *
     * @param titleId      ID of the title to refresh.
     * @param providerCode Optional provider code ("aniliberty", "animedia").
     *                     When null the backend picks the first known provider link.
     */
    suspend fun updateTitle(
        titleId: Int,
        providerCode: String? = null,
        forceRefresh: Boolean = false,
    ) {
        val params = buildMap<String, Any?> {
            put("title_ids", listOf(titleId))
            if (!providerCode.isNullOrBlank()) put("provider_code", providerCode)
            if (forceRefresh) put("force_refresh", true)
        }
        client.call("titles.update", params)
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
