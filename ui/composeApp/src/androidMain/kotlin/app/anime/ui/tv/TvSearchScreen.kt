package app.anime.ui.tv

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Search
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.tv.material3.*
import app.anime.data.dto.TitleCardDto
import app.anime.presentation.SearchUiState
import app.anime.ui.components.TvTitleCard

/**
 * TV search screen — D-pad optimised.
 * Large focus ring, 3-column grid (TV aspect ratio).
 */
@OptIn(ExperimentalTvMaterial3Api::class)
@Composable
fun TvSearchScreen(
    state: SearchUiState,
    onQueryChange: (String) -> Unit,
    onTitleClick: (TitleCardDto) -> Unit,
    onLoadMore: () -> Unit,
    onBack: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(start = 48.dp, top = 24.dp, end = 24.dp, bottom = 24.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад")
            }
            Spacer(Modifier.width(12.dp))
            // TV-optimised search field — remote control input
            OutlinedTextField(
                value = state.query,
                onValueChange = onQueryChange,
                placeholder = { Text("Поиск аниме...") },
                leadingIcon = { Icon(Icons.Default.Search, null) },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
        }

        Spacer(Modifier.height(16.dp))

        when {
            state.isLoading && state.results.isEmpty() -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }

            else -> {
                val gridState = rememberLazyGridState()

                LaunchedEffect(gridState) {
                    snapshotFlow { gridState.layoutInfo }
                        .collect { info ->
                            val lastVisible = info.visibleItemsInfo.lastOrNull()?.index ?: 0
                            val total = info.totalItemsCount
                            if (total > 0 && lastVisible >= total - 3 * 2) onLoadMore()
                        }
                }

                LazyVerticalGrid(
                    columns = GridCells.Fixed(3),   // TV: 3 wide cards per row
                    state = gridState,
                    contentPadding = PaddingValues(vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                    modifier = Modifier.weight(1f),
                ) {
                    items(state.results, key = { it.titleId }) { title ->
                        TvTitleCard(title = title, onClick = onTitleClick)
                    }
                }

                if (state.results.isNotEmpty()) {
                    Text(
                        text = "${state.results.size} из ${state.totalCount}",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
            }
        }
    }
}
