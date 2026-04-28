package app.anime.ui.components

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.anime.data.dto.RatingDto
import app.anime.data.dto.TitleCardDto
import app.anime.ui.theme.OnDarkSecondary
import coil3.compose.AsyncImage
import coil3.compose.LocalPlatformContext
import coil3.request.ImageRequest
import coil3.request.crossfade
import kotlin.math.roundToInt

/** Poster card used in grids, schedule rows, search results. */
@Composable
fun TitleCard(
    title: TitleCardDto,
    onClick: (TitleCardDto) -> Unit,
    modifier: Modifier = Modifier,
    width: Int = 130,
    height: Int = 195,
    subtitle: String? = null,
    subtitleMaxLines: Int = 1,
    enabled: Boolean = true,
) {
    val shape = RoundedCornerShape(8.dp)
    Card(
        modifier = modifier
            .width(width.dp)
            .then(if (enabled) Modifier.clickable { onClick(title) } else Modifier),
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

            val secondaryText = title.cardSubtitle(subtitle)
            val overlayHeight = when {
                subtitleMaxLines > 1 -> 96.dp
                secondaryText != null -> 82.dp
                else -> 72.dp
            }

            // Readable translucent backing behind title text.
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(overlayHeight)
                    .align(Alignment.BottomCenter)
                    .background(Color.Black.copy(alpha = 0.72f))
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
                if (secondaryText != null) {
                    Text(
                        text = secondaryText,
                        style = MaterialTheme.typography.bodySmall,
                        color = OnDarkSecondary,
                        maxLines = subtitleMaxLines,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }

            TitleStateBadges(
                ratingValue = title.ratingValue,
                externalRatings = title.externalRatingBadges(),
                isWatched = title.isWatched == true || title.allEpisodesWatched == true,
                needToSee = title.needToSee == true,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(4.dp)
                    .widthIn(max = (width * 0.68f).dp),
            )

            TitleTopStartBadges(
                providerLabel = title.provider?.takeIf { it.isNotBlank() },
                episodesCount = title.episodesCount?.takeIf { it > 0 },
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(4.dp),
            )
        }
    }
}

private fun TitleCardDto.cardSubtitle(explicitSubtitle: String?): String? {
    val parts = mutableListOf<String>()
    val scheduleText = explicitSubtitle ?: ongoingScheduleLabel()
    if (!scheduleText.isNullOrBlank()) {
        parts += scheduleText
    } else if (year != null) {
        parts += year.toString()
    }

    return parts.takeIf { it.isNotEmpty() }?.joinToString(" \u00b7 ")
}

private fun TitleCardDto.externalRatingBadges(): List<String> =
    ratings.mapNotNull { it.externalBadgeText() }.distinct().take(3)

private fun RatingDto.externalBadgeText(): String? {
    val score = scoreExternal ?: return null
    return score.formatExternalRatingScore()
}

private fun Double.formatExternalRatingScore(): String {
    val roundedTenths = (this * 10).roundToInt()
    val whole = roundedTenths / 10
    val fraction = roundedTenths % 10
    return "$whole.$fraction"
}

private fun TitleCardDto.ongoingScheduleLabel(): String? {
    val statusText = status ?: return null
    val isOngoing = statusText.contains("\u0440\u0430\u0431\u043e\u0442", ignoreCase = true) ||
        statusText.contains("ongoing", ignoreCase = true) ||
        statusText.contains("\u043e\u043d\u0433\u043e", ignoreCase = true)
    if (!isOngoing) return null

    val day = dayName?.takeIf { it.isNotBlank() } ?: dayOfWeek?.toDayName()
    return day?.let { "\u0412\u044b\u0445\u043e\u0434\u0438\u0442: $it" }
}

private fun Int.toDayName(): String? =
    when (this) {
        1 -> "\u041f\u043e\u043d\u0435\u0434\u0435\u043b\u044c\u043d\u0438\u043a"
        2 -> "\u0412\u0442\u043e\u0440\u043d\u0438\u043a"
        3 -> "\u0421\u0440\u0435\u0434\u0430"
        4 -> "\u0427\u0435\u0442\u0432\u0435\u0440\u0433"
        5 -> "\u041f\u044f\u0442\u043d\u0438\u0446\u0430"
        6 -> "\u0421\u0443\u0431\u0431\u043e\u0442\u0430"
        7 -> "\u0412\u043e\u0441\u043a\u0440\u0435\u0441\u0435\u043d\u044c\u0435"
        else -> null
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
@OptIn(ExperimentalLayoutApi::class)
private fun TitleStateBadges(
    ratingValue: Int?,
    externalRatings: List<String>,
    isWatched: Boolean,
    needToSee: Boolean,
    modifier: Modifier = Modifier,
) {
    if (ratingValue == null && externalRatings.isEmpty() && !isWatched && !needToSee) return

    FlowRow(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(3.dp),
        verticalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        if (ratingValue != null) {
            RatingBadge(text = ratingValue.toString())
        }
        externalRatings.forEach { rating ->
            RatingBadge(text = rating)
        }
        if (isWatched) {
            IconBadge(
                imageVector = Icons.Default.CheckCircle,
                contentDescription = "Просмотрено",
                containerColor = Color(0xFF2E7D32),
            )
        }
        if (needToSee) {
            IconBadge(
                imageVector = Icons.Default.Favorite,
                contentDescription = "В избранном",
                containerColor = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
private fun TitleTopStartBadges(
    providerLabel: String?,
    episodesCount: Int?,
    modifier: Modifier = Modifier,
) {
    if (providerLabel == null && episodesCount == null) return

    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(3.dp),
        horizontalAlignment = Alignment.Start,
    ) {
        if (providerLabel != null) {
            Surface(
                shape = RoundedCornerShape(4.dp),
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.92f),
                contentColor = MaterialTheme.colorScheme.onPrimary,
            ) {
                Text(
                    text = providerLabel,
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp),
                )
            }
        }
        if (episodesCount != null) {
            Surface(
                shape = RoundedCornerShape(4.dp),
                color = Color.Black.copy(alpha = 0.72f),
                contentColor = Color.White,
            ) {
                Text(
                    text = "$episodesCount эп.",
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp),
                )
            }
        }
    }
}

@Composable
private fun RatingBadge(text: String) {
    Surface(
        modifier = Modifier.widthIn(max = 92.dp),
        shape = RoundedCornerShape(4.dp),
        color = Color(0xFFE0A21A).copy(alpha = 0.95f),
        contentColor = Color.Black,
    ) {
        Row(
            modifier = Modifier
                .height(22.dp)
                .padding(horizontal = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(2.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Default.Star,
                contentDescription = "Рейтинг",
                modifier = Modifier.size(13.dp),
            )
            Text(
                text = text,
                style = MaterialTheme.typography.labelSmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun IconBadge(
    imageVector: ImageVector,
    contentDescription: String,
    containerColor: Color,
) {
    Surface(
        modifier = Modifier.size(22.dp),
        shape = RoundedCornerShape(4.dp),
        color = containerColor.copy(alpha = 0.92f),
        contentColor = Color.White,
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(
                imageVector = imageVector,
                contentDescription = contentDescription,
                modifier = Modifier.size(14.dp),
            )
        }
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
