package app.anime.ui.tv

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.tv.material3.*
import app.anime.data.dto.TitleCardDto
import app.anime.presentation.ScheduleUiState

/**
 * #8: Full-week schedule screen for Android TV.
 * D-pad navigable, TV material design.
 */
@OptIn(ExperimentalTvMaterial3Api::class)
@Composable
fun TvScheduleScreen(
    state: ScheduleUiState,
    onTitleClick: (TitleCardDto) -> Unit,
    onRefresh: () -> Unit,
    onBack: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(start = 48.dp, top = 24.dp, end = 24.dp, bottom = 24.dp),
    ) {
        // Top bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                    Spacer(Modifier.width(8.dp))
                    Text("Назад")
                }
                Text(
                    "Расписание выхода",
                    style = MaterialTheme.typography.headlineLarge,
                    color = Color.White,
                )
            }
            Button(onClick = onRefresh) {
                Icon(Icons.Default.Refresh, null)
            }
        }

        Spacer(Modifier.height(24.dp))

        when {
            state.isLoading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }

            state.error != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(state.error, color = Color.Red)
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = onRefresh) { Text("Повторить") }
                }
            }

            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(32.dp)) {
                items(state.days, key = { it.day }) { dayState ->
                    TvContentRow(
                        title = dayState.dayName,
                        items = dayState.entries.map { TitleCardDto(titleId = it.titleId) },
                        onItemClick = onTitleClick,
                    )
                }
            }
        }
    }
}
