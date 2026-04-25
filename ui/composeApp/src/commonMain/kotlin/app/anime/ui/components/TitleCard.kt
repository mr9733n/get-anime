package app.anime.ui.components

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.anime.data.dto.TitleCardDto
import app.anime.ui.theme.OnDarkSecondary
import coil3.compose.AsyncImage
import coil3.compose.LocalPlatformContext
import coil3.request.ImageRequest
import coil3.request.crossfade

/** Poster card used in grids, schedule rows, search results. */
@Composable
fun TitleCard(
    title: TitleCardDto,
    onClick: (TitleCardDto) -> Unit,
    modifier: Modifier = Modifier,
    width: Int = 130,
    height: Int = 195,
) {
    val shape = RoundedCornerShape(8.dp)
    Card(
        modifier = modifier
            .width(width.dp)
            .clickable { onClick(title) },
        shape = shape,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
    ) {
        Box(modifier = Modifier.height(height.dp)) {
            // Poster image — use AsyncImage when Coil is added; placeholder for now
            PosterImage(
                url = title.posterUrl,
                contentDescription = title.nameRu ?: title.nameEn,
                modifier = Modifier.fillMaxSize(),
            )

            // Gradient overlay + title text at bottom
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(72.dp)
                    .align(Alignment.BottomCenter)
                    .background(
                        Brush.verticalGradient(
                            colors = listOf(Color.Transparent, Color(0xCC000000))
                        )
                    )
            )
            Column(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(horizontal = 6.dp, vertical = 4.dp)
            ) {
                Text(
                    text = title.nameRu ?: title.nameEn ?: "—",
                    style = MaterialTheme.typography.labelMedium,
                    color = Color.White,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                if (title.year != null) {
                    Text(
                        text = "${title.year}",
                        style = MaterialTheme.typography.bodySmall,
                        color = OnDarkSecondary,
                    )
                }
            }

            // Watchlist badge
            if (title.needToSee == true) {
                WatchlistBadge(modifier = Modifier.align(Alignment.TopEnd).padding(4.dp))
            }
        }
    }
}

/** TV-focused card — larger, with visible focus ring. */
@Composable
fun TvTitleCard(
    title: TitleCardDto,
    onClick: (TitleCardDto) -> Unit,
    modifier: Modifier = Modifier,
) {
    TitleCard(
        title = title,
        onClick = onClick,
        modifier = modifier,
        width = 160,
        height = 240,
    )
}

@Composable
private fun WatchlistBadge(modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(4.dp),
        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.9f),
    ) {
        Text(
            text = "★",
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
            color = Color.White,
        )
    }
}

/** Async poster image using Coil3 KMP. Falls back to a 🎬 placeholder. */
@Composable
fun PosterImage(
    url: String?,
    contentDescription: String?,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier.background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        if (url != null) {
            val context = LocalPlatformContext.current
            AsyncImage(
                model = ImageRequest.Builder(context)
                    .data(url)
                    .crossfade(true)
                    .build(),
                contentDescription = contentDescription,
                contentScale = ContentScale.Crop,
                modifier = Modifier.matchParentSize(),
            )
        } else {
            Text("🎬", style = MaterialTheme.typography.headlineLarge)
        }
    }
}
