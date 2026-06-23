package app.anime.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.anime.data.dto.EpisodeDto
import app.anime.data.dto.FranchiseDto
import app.anime.data.dto.ProviderLinkDto
import app.anime.data.dto.RatingDto
import app.anime.data.dto.TeamMemberDto
import app.anime.data.dto.TitleDetailsDto
import app.anime.data.dto.TorrentDto
import app.anime.presentation.TitleDetailUiState
import app.anime.presentation.UpdateState
import app.anime.ui.components.EpisodeRow
import app.anime.ui.components.PosterImage
import kotlin.math.roundToInt

data class TitleFacet(
    val title: String,
    val year: Int? = null,
    val genre: String = "",
    val status: String = "",
    val teamMemberId: Int? = null,
    val teamMember: String = "",
    val franchiseId: Int? = null,
    val franchise: String = "",
)

@Composable
fun TitleDetailScreen(
    state: TitleDetailUiState,
    updateState: UpdateState = UpdateState.Idle,
    onBack: () -> Unit,
    onEpisodePlay: (EpisodeDto) -> Unit,
    onEpisodeToggleWatched: (EpisodeDto) -> Unit,
    onToggleNeedToSee: () -> Unit,
    onMarkAllWatched: () -> Unit,
    onUpdateFromProvider: () -> Unit = {},
    onForceUpdateEpisodes: () -> Unit = {},
    onDismissUpdateResult: () -> Unit = {},
    onPlayAll: () -> Unit = {},
    onRelatedTitleClick: (Int) -> Unit = {},
    onFacetClick: (TitleFacet) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    when (state) {
        is TitleDetailUiState.Loading -> {
            Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }

        is TitleDetailUiState.Error -> {
            Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(state.message, color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(8.dp))
                    TextButton(onClick = onBack) { Text("Назад") }
                }
            }
        }

        is TitleDetailUiState.Success -> {
            TitleDetailContent(
                title = state.title,
                updateState = updateState,
                onBack = onBack,
                onEpisodePlay = onEpisodePlay,
                onEpisodeToggleWatched = onEpisodeToggleWatched,
                onToggleNeedToSee = onToggleNeedToSee,
                onMarkAllWatched = onMarkAllWatched,
                onUpdateFromProvider = onUpdateFromProvider,
                onForceUpdateEpisodes = onForceUpdateEpisodes,
                onDismissUpdateResult = onDismissUpdateResult,
                onPlayAll = onPlayAll,
                onRelatedTitleClick = onRelatedTitleClick,
                onFacetClick = onFacetClick,
                modifier = modifier,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun TitleDetailContent(
    title: TitleDetailsDto,
    updateState: UpdateState,
    onBack: () -> Unit,
    onEpisodePlay: (EpisodeDto) -> Unit,
    onEpisodeToggleWatched: (EpisodeDto) -> Unit,
    onToggleNeedToSee: () -> Unit,
    onMarkAllWatched: () -> Unit,
    onUpdateFromProvider: () -> Unit,
    onForceUpdateEpisodes: () -> Unit,
    onDismissUpdateResult: () -> Unit,
    onPlayAll: () -> Unit = {},
    onRelatedTitleClick: (Int) -> Unit = {},
    onFacetClick: (TitleFacet) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    // Auto-dismiss "Done" state after 2 seconds
    LaunchedEffect(updateState) {
        if (updateState is UpdateState.Done) {
            kotlinx.coroutines.delay(2_000)
            onDismissUpdateResult()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title.nameRu ?: title.nameEn ?: "—") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад")
                    }
                },
                actions = {
                    // Play all episodes as a playlist — only when at least one episode has a
                    // direct HLS stream (web-player-only titles can't form a local playlist).
                    val hasStreamableEpisodes = title.episodes.any { ep ->
                        ep.hlsSd != null || ep.hlsHd != null || ep.hlsFhd != null
                    }
                    if (hasStreamableEpisodes) {
                        IconButton(
                            onClick = onPlayAll,
                            enabled = updateState !is UpdateState.Loading,
                        ) {
                            Icon(Icons.Default.PlayArrow, contentDescription = "Воспроизвести все")
                        }
                    }
                    // #3: Update from provider button
                    IconButton(
                        onClick = onUpdateFromProvider,
                        enabled = updateState !is UpdateState.Loading,
                    ) {
                        if (updateState is UpdateState.Loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                strokeWidth = 2.dp,
                            )
                        } else {
                            Icon(Icons.Default.Refresh, contentDescription = "Обновить из провайдера")
                        }
                    }
                    val hasAniMediaProvider = title.providerLinks.any {
                        it.providerCode.equals("animedia", ignoreCase = true)
                    }
                    if (hasAniMediaProvider) {
                        IconButton(
                            onClick = onForceUpdateEpisodes,
                            enabled = updateState !is UpdateState.Loading,
                        ) {
                            Icon(
                                Icons.Default.Refresh,
                                contentDescription = "Force refresh AniMedia episodes",
                                tint = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                    // Watchlist toggle
                    IconButton(onClick = onToggleNeedToSee) {
                        Icon(
                            imageVector = if (title.needToSee == true)
                                Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                            contentDescription = "Вотч-лист",
                            tint = if (title.needToSee == true)
                                MaterialTheme.colorScheme.primary
                            else
                                MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    // Mark all watched
                    IconButton(onClick = onMarkAllWatched) {
                        Icon(Icons.Default.Done, contentDescription = "Отметить все")
                    }
                },
            )
        },
        // #3: Update result snackbar
        snackbarHost = {
            when (updateState) {
                is UpdateState.Done ->
                    Snackbar { Text("✓ Данные обновлены из провайдера") }
                is UpdateState.Error ->
                    Snackbar(
                        action = { TextButton(onClick = onDismissUpdateResult) { Text("OK") } }
                    ) { Text("Ошибка обновления: ${updateState.message}") }
                else -> {}
            }
        },
        modifier = modifier,
    ) { padding ->
        TitleDetailBody(
            title = title,
            contentPadding = padding,
            onEpisodePlay = onEpisodePlay,
            onEpisodeToggleWatched = onEpisodeToggleWatched,
            onRelatedTitleClick = onRelatedTitleClick,
            onFacetClick = onFacetClick,
        )
    }
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun TitleDetailBody(
    title: TitleDetailsDto,
    contentPadding: PaddingValues,
    onEpisodePlay: (EpisodeDto) -> Unit,
    onEpisodeToggleWatched: (EpisodeDto) -> Unit,
    onRelatedTitleClick: (Int) -> Unit,
    onFacetClick: (TitleFacet) -> Unit,
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding)
            .padding(16.dp),
    ) {
        val isWide = maxWidth >= 860.dp
        if (isWide) {
            Row(
                modifier = Modifier.fillMaxSize(),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                TitleSideRail(
                    title = title,
                    onFacetClick = onFacetClick,
                    modifier = Modifier.width(216.dp),
                )
                TitleMainColumn(
                    title = title,
                    onEpisodePlay = onEpisodePlay,
                    onEpisodeToggleWatched = onEpisodeToggleWatched,
                    onRelatedTitleClick = onRelatedTitleClick,
                    onFacetClick = onFacetClick,
                    modifier = Modifier.weight(1f),
                )
            }
        } else {
            TitleMainColumn(
                title = title,
                onEpisodePlay = onEpisodePlay,
                onEpisodeToggleWatched = onEpisodeToggleWatched,
                onRelatedTitleClick = onRelatedTitleClick,
                onFacetClick = onFacetClick,
                modifier = Modifier.fillMaxSize(),
                includePoster = true,
                includeFacetBlock = true,
                includeFacts = true,
            )
        }
    }
}

@Composable
private fun TitleMainColumn(
    title: TitleDetailsDto,
    onEpisodePlay: (EpisodeDto) -> Unit,
    onEpisodeToggleWatched: (EpisodeDto) -> Unit,
    onRelatedTitleClick: (Int) -> Unit,
    onFacetClick: (TitleFacet) -> Unit,
    modifier: Modifier = Modifier,
    includePoster: Boolean = false,
    includeFacetBlock: Boolean = false,
    includeFacts: Boolean = false,
) {
    val description = title.description?.takeIf { it.isNotBlank() }
    LazyColumn(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (includePoster) {
            item {
                Box(
                    modifier = Modifier.fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) {
                    PosterImage(
                        url = title.posterUrl,
                        contentDescription = title.nameRu,
                        modifier = Modifier
                            .width(200.dp)
                            .height(280.dp),
                    )
                }
            }
        }
        if (description != null) {
            item {
                DescriptionSection(description = description)
            }
        }
        if (includeFacetBlock) {
            item {
                HeaderFacetBlock(
                    title = title,
                    onFacetClick = onFacetClick,
                )
            }
        }
        if (includeFacts) {
            item {
                TitleFactsBlock(title = title)
            }
        }
        item {
            TitleMetadataSection(
                title = title,
                onRelatedTitleClick = onRelatedTitleClick,
                onFacetClick = onFacetClick,
            )
        }

        if (title.torrents.isNotEmpty()) {
            item {
                TorrentsSection(torrents = title.torrents)
            }
        }

        if (title.episodes.isNotEmpty()) {
            item {
                Text(
                    text = "Эпизоды (${title.episodes.size})",
                    style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier.padding(top = 4.dp, bottom = 2.dp),
                )
            }
            items(title.episodes, key = { it.episodeId }) { ep ->
                EpisodeRow(
                    episode = ep,
                    onPlay = onEpisodePlay,
                    onToggleWatched = onEpisodeToggleWatched,
                )
            }
        }
    }
}

@Composable
private fun TitleSideRail(
    title: TitleDetailsDto,
    onFacetClick: (TitleFacet) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        PosterImage(
            url = title.posterUrl,
            contentDescription = title.nameRu,
            modifier = Modifier
                .width(200.dp)
                .height(280.dp),
        )
        HeaderFacetBlock(
            title = title,
            onFacetClick = onFacetClick,
        )
        TitleFactsBlock(title = title)
    }
}

@Composable
private fun DescriptionSection(description: String) {
    SectionSurface(title = "Описание") {
        Text(
            text = description,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun SectionSurface(
    title: String? = null,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.small,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.32f),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (title != null) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
            content()
        }
    }
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun HeaderFacetBlock(
    title: TitleDetailsDto,
    onFacetClick: (TitleFacet) -> Unit,
) {
    SectionSurface(title = "Каталог") {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            MetaChip(
                text = title.year?.toString(),
                onClick = title.year?.let { year ->
                    { onFacetClick(TitleFacet(title = "Год: $year", year = year)) }
                },
            )
            MetaChip(title.type)
            MetaChip(
                text = title.status,
                onClick = title.status?.takeIf { it.isNotBlank() }?.let { status ->
                    { onFacetClick(TitleFacet(title = "Статус: $status", status = status)) }
                },
            )
            title.genres.distinct().forEach { genre ->
                FacetChip(
                    text = genre,
                    onClick = {
                        onFacetClick(TitleFacet(title = "Жанр: $genre", genre = genre))
                    },
                )
            }
        }
    }
}

private data class TitleFacts(
    val watchedText: String,
    val ratingLines: List<String>,
    val providerLines: List<String>,
)

private fun TitleDetailsDto.toTitleFacts(): TitleFacts {
    val hasEpisodeState = episodes.isNotEmpty()
    val watchedEpisodeCount = if (hasEpisodeState) {
        episodes.count { it.isWatched == true }
    } else {
        watchedEpisodeCount ?: 0
    }
    val totalEpisodes = episodes.size
    val allEpisodesWatched = if (hasEpisodeState) {
        watchedEpisodeCount == totalEpisodes
    } else {
        allEpisodesWatched == true
    }
    val explicitTitleWatched = isWatched == true ||
        historyRecords.any { it.episodeId == null && it.isWatched }
    val watchedText = when {
        allEpisodesWatched || (!hasEpisodeState && explicitTitleWatched) -> "Тайтл просмотрен"
        watchedEpisodeCount > 0 && totalEpisodes > 0 ->
            "Просмотрено ${formatEpisodeCount(watchedEpisodeCount)}"
        else -> "Тайтл не просмотрен"
    }
    return TitleFacts(
        watchedText = watchedText,
        ratingLines = ratings
            .flatMap { rating -> listOfNotNull(formatPrimaryRating(rating), formatExternalRating(rating)) }
            .distinct(),
        providerLines = providerLinks.mapNotNull(::formatProviderLink).distinct(),
    )
}

@Composable
private fun TitleFactsBlock(title: TitleDetailsDto) {
    val facts = title.toTitleFacts()
    SectionSurface(title = "Сведения") {
        MetadataLine(label = "Просмотр", value = facts.watchedText, compact = true)
        if (facts.ratingLines.isNotEmpty()) {
            MetadataLine(label = "Рейтинг", value = facts.ratingLines.joinToString(", "), compact = true)
        }
        MetadataLine(label = "ID", value = title.titleId.toString(), compact = true)
        if (facts.providerLines.isNotEmpty()) {
            MetadataLine(label = "Провайдеры", value = facts.providerLines.joinToString("\n"), compact = true)
        }
    }
}

@Composable
private fun TitleMetadataSection(
    title: TitleDetailsDto,
    onRelatedTitleClick: (Int) -> Unit,
    onFacetClick: (TitleFacet) -> Unit,
) {
    val franchiseLines = title.franchises
        .sortedBy { it.ordinal ?: Int.MAX_VALUE }
        .mapNotNull(::formatFranchise)
        .distinct()
    val teamGroups = title.teamMembers.toLegacyTeamGroups()
    val franchiseTitleLinks = title.franchises
        .mapNotNull { it.toRelatedTitleLink(currentTitleId = title.titleId) }
        .distinctBy { it.titleId }
    val teamFacets = title.teamMembers.toTeamFacets()
    val franchiseFacets = title.franchises.toFranchiseFacets()
    val hasTeam = teamGroups.isNotEmpty()
    val hasFranchise = franchiseFacets.isNotEmpty() || franchiseLines.isNotEmpty() || franchiseTitleLinks.isNotEmpty()

    if (!hasTeam && !hasFranchise) return

    SectionSurface(title = "Команда и связи") {
        teamGroups["Озвучка"]?.let { names ->
            MetadataFacetChipsLine(
                label = "Озвучка",
                chips = names.mapNotNull { name -> teamFacets[name] },
                fallbackValue = names.joinToString(", "),
                onClick = onFacetClick,
            )
        }
        teamGroups["Перевод"]?.let { names ->
            MetadataFacetChipsLine(
                label = "Перевод",
                chips = names.mapNotNull { name -> teamFacets[name] },
                fallbackValue = names.joinToString(", "),
                onClick = onFacetClick,
            )
        }
        if (franchiseFacets.isNotEmpty()) {
            MetadataFacetChipsLine(
                label = "Франшиза",
                chips = franchiseFacets,
                fallbackValue = franchiseLines.joinToString("\n"),
                onClick = onFacetClick,
            )
            if (franchiseTitleLinks.isNotEmpty()) {
                MetadataLinkedTitlesLine(
                    label = "Тайтлы франшизы",
                    links = franchiseTitleLinks,
                    onClick = onRelatedTitleClick,
                )
            }
        } else if (franchiseLines.isNotEmpty()) {
            MetadataLine(label = "Франшизы", value = franchiseLines.joinToString("\n"))
        }
    }
}

@Composable
private fun MetadataLine(label: String, value: String, compact: Boolean = false) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = if (compact) MaterialTheme.typography.bodySmall else MaterialTheme.typography.bodyMedium,
            color = if (compact) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
        )
    }
}

private fun formatPrimaryRating(rating: RatingDto): String? {
    val value = rating.ratingValue?.toString() ?: return null
    val name = rating.ratingName ?: "Рейтинг"
    return "$name: $value"
}

private fun formatExternalRating(rating: RatingDto): String? {
    val value = rating.scoreExternal?.formatRatingScore() ?: return null
    val name = rating.nameExternal?.takeIf { it.isNotBlank() } ?: return null
    return "$name: $value"
}

private fun Double.formatRatingScore(): String {
    val roundedTenths = (this * 10).roundToInt()
    val whole = roundedTenths / 10
    val fraction = roundedTenths % 10
    return if (fraction == 0) whole.toString() else "$whole.$fraction"
}

private fun formatFranchise(franchise: FranchiseDto): String? {
    val name = franchise.nameRu
        ?: franchise.nameEn
        ?: franchise.nameAlternative
        ?: franchise.franchiseName
        ?: franchise.code
        ?: return null
    return franchise.ordinal?.let { "$it. $name" } ?: name
}

private data class RelatedTitleLink(
    val titleId: Int,
    val label: String,
    val ordinal: Int?,
)

private fun FranchiseDto.toRelatedTitleLink(currentTitleId: Int): RelatedTitleLink? {
    val id = relatedTitleId?.takeIf { it > 0 && it != currentTitleId } ?: return null
    val name = relatedTitleNameRu
        ?: relatedTitleNameEn
        ?: nameRu
        ?: nameEn
        ?: nameAlternative
        ?: franchiseName
        ?: code
        ?: return null
    val label = ordinal?.let { "$it. $name" } ?: name
    return RelatedTitleLink(titleId = id, label = label, ordinal = ordinal)
}

private fun List<TeamMemberDto>.toLegacyTeamGroups(): Map<String, List<String>> {
    val grouped = linkedMapOf<String, MutableList<String>>()
    for (member in this) {
        val label = when {
            member.role.contains("voice", ignoreCase = true) -> "Озвучка"
            member.role.contains("translator", ignoreCase = true) ||
                member.role.contains("translat", ignoreCase = true) -> "Перевод"
            else -> null
        } ?: continue
        grouped.getOrPut(label) { mutableListOf() }.add(member.name)
    }
    return grouped.mapValues { (_, names) -> names.distinct() }
}

private fun List<TeamMemberDto>.toTeamFacets(): Map<String, TitleFacet> =
    distinctBy { it.id ?: it.name }
        .associate { member ->
            member.name to TitleFacet(
                title = "Команда: ${member.name}",
                teamMemberId = member.id,
                teamMember = member.name,
            )
        }

private fun List<FranchiseDto>.toFranchiseFacets(): List<TitleFacet> =
    mapNotNull { franchise ->
        val id = franchise.franchiseId?.takeIf { it > 0 } ?: return@mapNotNull null
        val name = franchise.franchiseName
            ?: franchise.nameRu
            ?: franchise.nameEn
            ?: franchise.nameAlternative
            ?: franchise.code
            ?: return@mapNotNull null
        TitleFacet(
            title = "Франшиза: $name",
            franchiseId = id,
            franchise = name,
        )
    }.distinctBy { it.franchiseId }

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun MetadataFacetChipsLine(
    label: String,
    chips: List<TitleFacet>,
    fallbackValue: String,
    onClick: (TitleFacet) -> Unit,
) {
    if (chips.isEmpty()) {
        MetadataLine(label = label, value = fallbackValue)
        return
    }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            chips.forEach { facet ->
                FacetChip(
                    text = when {
                        facet.teamMember.isNotBlank() -> facet.teamMember
                        facet.franchise.isNotBlank() -> facet.franchise
                        else -> facet.title
                    },
                    onClick = { onClick(facet) },
                )
            }
        }
    }
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun MetadataLinkedTitlesLine(
    label: String,
    links: List<RelatedTitleLink>,
    onClick: (Int) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            links.sortedWith(compareBy<RelatedTitleLink> { it.ordinal ?: Int.MAX_VALUE }.thenBy { it.label })
                .forEach { link ->
                    CompactChip(
                        text = link.label,
                        onClick = { onClick(link.titleId) },
                    )
                }
        }
    }
}

private fun formatProviderLink(link: ProviderLinkDto): String? {
    val name = link.providerName?.takeIf { it.isNotBlank() }
        ?: link.providerCode.takeIf { it.isNotBlank() }
        ?: return null
    return link.externalTitleId
        .takeIf { it.isNotBlank() }
        ?.let { "$name: $it" }
        ?: name
}

@Composable
private fun TorrentsSection(torrents: List<TorrentDto>) {
    SectionSurface(title = "Торренты (${torrents.size})") {
        torrents.sortedWith(compareBy<TorrentDto> { it.rangeFirst ?: Int.MAX_VALUE }
            .thenByDescending { it.seeders ?: -1 }
            .thenBy { it.torrentId })
            .forEach { torrent ->
                TorrentRow(torrent = torrent)
            }
    }
}

@Composable
private fun TorrentRow(torrent: TorrentDto) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        tonalElevation = 1.dp,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = torrent.primaryTorrentText(),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurface,
            )
            torrent.secondaryTorrentText()?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            torrent.statsTorrentText()?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

private fun TorrentDto.primaryTorrentText(): String =
    listOfNotNull(
        qualityType?.takeIf { it.isNotBlank() },
        quality?.takeIf { it.isNotBlank() },
        resolution?.takeIf { it.isNotBlank() },
        encoder?.takeIf { it.isNotBlank() },
        episodesRange?.takeIf { it.isNotBlank() },
        sizeString?.takeIf { it.isNotBlank() }?.let { "($it)" },
    ).takeIf { it.isNotEmpty() }?.joinToString(" · ")
        ?: label?.takeIf { it.isNotBlank() }
        ?: filename?.takeIf { it.isNotBlank() }
        ?: "Torrent #$torrentId"

private fun TorrentDto.secondaryTorrentText(): String? =
    listOfNotNull(
        filename?.takeIf { it.isNotBlank() },
        hash?.takeIf { it.isNotBlank() }?.let { "hash: ${it.take(12)}" },
        when {
            !url.isNullOrBlank() -> "torrent file"
            !magnetLink.isNullOrBlank() -> "magnet"
            else -> null
        },
    ).takeIf { it.isNotEmpty() }?.joinToString(" · ")

private fun TorrentDto.statsTorrentText(): String? =
    listOfNotNull(
        seeders?.let { "S $it" },
        leechers?.let { "L $it" },
        downloads?.let { "D $it" },
    ).takeIf { it.isNotEmpty() }?.joinToString(" · ")

private fun formatEpisodeCount(count: Int): String {
    val mod100 = count % 100
    val mod10 = count % 10
    val word = when {
        mod100 in 11..14 -> "серий"
        mod10 == 1 -> "серия"
        mod10 in 2..4 -> "серии"
        else -> "серий"
    }
    return "$count $word"
}

@Composable
private fun FacetChip(
    text: String,
    onClick: () -> Unit,
) {
    CompactChip(text = text, onClick = onClick)
}

@Composable
private fun MetaChip(text: String?, onClick: (() -> Unit)? = null) {
    if (text.isNullOrBlank()) return
    if (onClick != null) {
        CompactChip(text = text, onClick = onClick)
        return
    }
    CompactChip(text = text)
}

@Composable
private fun CompactChip(
    text: String,
    onClick: (() -> Unit)? = null,
) {
    val chipModifier = if (onClick != null) {
        Modifier.clickable(onClick = onClick)
    } else {
        Modifier
    }
    Surface(
        shape = RoundedCornerShape(4.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.65f)),
        modifier = chipModifier,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = 1,
        )
    }
}
