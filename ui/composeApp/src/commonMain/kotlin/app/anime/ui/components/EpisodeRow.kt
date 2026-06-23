package app.anime.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.anime.data.dto.EpisodeDto

@Composable
fun EpisodeRow(
    episode: EpisodeDto,
    onPlay: (EpisodeDto) -> Unit,
    onToggleWatched: (EpisodeDto) -> Unit,
    modifier: Modifier = Modifier,
) {
    val watched = episode.isWatched == true
    val bg = if (watched)
        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
    else
        MaterialTheme.colorScheme.surface

    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(bg)
            .clickable { onPlay(episode) }
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Episode number badge
        Surface(
            shape = RoundedCornerShape(4.dp),
            color = MaterialTheme.colorScheme.primaryContainer,
            modifier = Modifier.size(36.dp),
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = episode.episodeNumber.toString(),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onPrimary,
                )
            }
        }

        Spacer(Modifier.width(12.dp))

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = episode.title ?: "Эпизод ${episode.episodeNumber}",
                style = MaterialTheme.typography.titleSmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }

        Spacer(Modifier.width(8.dp))

        // Watched toggle
        IconButton(onClick = { onToggleWatched(episode) }) {
            Icon(
                imageVector = Icons.Default.Check,
                contentDescription = if (watched) "Снять отметку" else "Отметить просмотренным",
                tint = if (watched) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        // Play button
        FilledIconButton(onClick = { onPlay(episode) }) {
            Icon(
                imageVector = Icons.Default.PlayArrow,
                contentDescription = "Смотреть",
            )
        }
    }
}
