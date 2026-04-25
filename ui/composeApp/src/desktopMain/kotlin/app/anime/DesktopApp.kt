package app.anime

import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.CreationExtras
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import app.anime.data.AnimeRepository
import app.anime.data.AppSettings
import app.anime.data.HttpBackendClient
import app.anime.presentation.*
import app.anime.ui.screens.*
import app.anime.ui.theme.AnimePlayerTheme
import kotlin.reflect.KClass

private object Route {
    const val SEARCH   = "search"
    const val SETTINGS = "settings"
    fun title(id: Int) = "title/$id"
    const val TITLE    = "title/{titleId}"
}

@Composable
fun DesktopApp(
    repo: AnimeRepository,
    settings: AppSettings,
    onBackendUrlChange: (String) -> Unit,
) {
    AnimePlayerTheme {
        Surface {
            val navController = rememberNavController()

            NavHost(navController = navController, startDestination = Route.SEARCH) {

                composable(Route.SEARCH) {
                    val vm: SearchViewModel = viewModel(
                        factory = remember(repo) { vmFactory { SearchViewModel(repo) } }
                    )
                    val state by vm.state.collectAsState()
                    SearchScreen(
                        state = state,
                        onQueryChange = vm::onQueryChange,
                        onTitleClick = { navController.navigate(Route.title(it.titleId)) },
                        onLoadMore = vm::loadMore,
                        columns = 6,
                        onSettingsClick = { navController.navigate(Route.SETTINGS) },
                    )
                }

                composable(Route.SETTINGS) {
                    SettingsScreen(
                        settings = settings,
                        onBack = { navController.popBackStack() },
                        onConnectionTest = { url ->
                            runCatching {
                                val t = HttpBackendClient(url)
                                t.call("titles.search", mapOf("query" to "", "limit" to 1))
                                t.close()
                                true
                            }.getOrDefault(false)
                        },
                    )
                }

                composable(
                    route = Route.TITLE,
                    arguments = listOf(navArgument("titleId") { type = NavType.IntType })
                ) { backStackEntry ->
                    val titleId = backStackEntry.arguments!!.getInt("titleId")
                    val vm: TitleViewModel = viewModel(
                        key = "title_$titleId",
                        factory = remember(repo, titleId) { vmFactory { TitleViewModel(repo, titleId) } },
                    )
                    val state by vm.uiState.collectAsState()

                    LaunchedEffect(vm) {
                        vm.playerEvent.collect { event ->
                            if (event is PlayerLaunchEvent.Launch) {
                                launchPlayer(settings.playerCommand, event.streamUrl)
                            }
                        }
                    }

                    TitleDetailScreen(
                        state = state,
                        onBack = { navController.popBackStack() },
                        onEpisodePlay = vm::onEpisodeClick,
                        onEpisodeToggleWatched = { ep ->
                            vm.markEpisodeWatched(ep, ep.isWatched != true)
                        },
                        onToggleNeedToSee = vm::toggleNeedToSee,
                        onMarkAllWatched = { vm.markAllWatched(true) },
                    )
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// ViewModelProvider.Factory helper — KMP uses KClass<T>, not Class<T>
// ---------------------------------------------------------------------------
private inline fun <reified T : ViewModel> vmFactory(
    crossinline create: () -> T,
): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
    override fun <VM : ViewModel> create(modelClass: KClass<VM>, extras: CreationExtras): VM {
        @Suppress("UNCHECKED_CAST")
        return create() as VM
    }
}

// ---------------------------------------------------------------------------
// Player launch
// ---------------------------------------------------------------------------
private fun launchPlayer(playerCommand: String, url: String) {
    val parts = playerCommand.trim().split("\\s+".toRegex()) + url
    try {
        ProcessBuilder(parts).inheritIO().start()
    } catch (_: Exception) {
        val os = System.getProperty("os.name").lowercase()
        val fallback = when {
            os.contains("win") -> listOf("cmd", "/c", "start", url)
            os.contains("mac") -> listOf("open", url)
            else               -> listOf("xdg-open", url)
        }
        runCatching { ProcessBuilder(fallback).start() }
    }
}
