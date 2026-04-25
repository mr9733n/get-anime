package app.anime.ui.screens

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
import app.anime.data.dto.TitleDetailsDto
import app.anime.presentation.TitleDetailUiState
import app.anime.presentation.UpdateState
import app.anime.ui.components.EpisodeRow
import app.anime.ui.components.PosterImage

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
    onDismissUpdateResult: () -> Unit = {},
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
                onDismissUpdateResult = onDismissUpdateResult,
                modifier = modifier,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
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
    onDismissUpdateResult: () -> Unit,
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
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Left: poster + meta
            Column(modifier = Modifier.width(200.dp)) {
                PosterImage(
                    url = title.posterUrl,
                    contentDescription = title.nameRu,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(280.dp)
                        .then(Modifier),
                )
                Spacer(Modifier.height(12.dp))
                MetaChip(title.year?.toString())
                MetaChip(title.type)
                MetaChip(title.status)
                if (title.genres.isNotEmpty()) {
                    Text(
                        text = title.genres.joinToString(", "),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
            }

            // Right: description + episodes
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (!title.description.isNullOrBlank()) {
                    item {
                        Text(
                            text = title.description,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }

                if (title.episodes.isNotEmpty()) {
                    item {
                        Text(
                            text = "Эпизоды (${title.episodes.size})",
                            style = MaterialTheme.typography.headlineMedium,
                            modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
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
    }
}

@Composable
private fun MetaChip(text: String?) {
    if (text.isNullOrBlank()) return
    Surface(
        shape = RoundedCornerShape(4.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.padding(bottom = 4.dp),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
