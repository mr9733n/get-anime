package app.anime

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.CreationExtras
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import androidx.tv.material3.*
import app.anime.data.AnimeRepository
import app.anime.data.AppSettings
import app.anime.presentation.*
import app.anime.ui.screens.SettingsScreen
import app.anime.ui.screens.TitleDetailScreen
import app.anime.ui.tv.TvHomeScreen
import app.anime.ui.tv.TvSearchScreen
import kotlin.reflect.KClass

private object TvRoute {
    const val HOME     = "home"
    const val SEARCH   = "search"
    const val SETTINGS = "settings"
    fun title(id: Int) = "title/$id"
    const val TITLE    = "title/{titleId}"
}

@OptIn(ExperimentalTvMaterial3Api::class)
@Composable
fun TvApp(
    repo: AnimeRepository,
    settings: AppSettings,
    onPlayStream: (String) -> Unit,
    onBackendUrlChange: (String) -> Unit,
) {
    MaterialTheme {
        val navController = rememberNavController()

        NavHost(
            navController = navController,
            startDestination = TvRoute.HOME,
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF0F0F0F)),
        ) {

            composable(TvRoute.HOME) {
                val vm: HomeViewModel = viewModel(
                    factory = remember(repo) { vmFactory { HomeViewModel(repo) } }
                )
                val state by vm.state.collectAsState()
                TvHomeScreen(
                    state = state,
                    onTitleClick = { navController.navigate(TvRoute.title(it.titleId)) },
                    onSearchClick = { navController.navigate(TvRoute.SEARCH) },
                    onSettingsClick = { navController.navigate(TvRoute.SETTINGS) },
                    onRefresh = vm::refresh,
                )
            }

            composable(TvRoute.SEARCH) {
                val vm: SearchViewModel = viewModel(
                    factory = remember(repo) { vmFactory { SearchViewModel(repo) } }
                )
                val state by vm.state.collectAsState()
                TvSearchScreen(
                    state = state,
                    onQueryChange = vm::onQueryChange,
                    onTitleClick = { navController.navigate(TvRoute.title(it.titleId)) },
                    onLoadMore = vm::loadMore,
                    onBack = { navController.popBackStack() },
                )
            }

            composable(TvRoute.SETTINGS) {
                SettingsScreen(
                    settings = settings,
                    onBack = { navController.popBackStack() },
                    onConnectionTest = { url ->
                        runCatching {
                            val t = app.anime.data.HttpBackendClient(url)
                            t.call("titles.search", mapOf("query" to "", "limit" to 1))
                            t.close()
                            true
                        }.getOrDefault(false)
                    },
                )
            }

            composable(
                route = TvRoute.TITLE,
                arguments = listOf(navArgument("titleId") { type = NavType.IntType }),
            ) { backStackEntry ->
                val titleId = backStackEntry.arguments!!.getInt("titleId")
                val vm: TitleViewModel = viewModel(
                    key = "title_$titleId",
                    factory = remember(repo, titleId) { vmFactory { TitleViewModel(repo, titleId) } },
                )
                val state by vm.uiState.collectAsState()

                LaunchedEffect(vm) {
                    vm.playerEvent.collect { event ->
                        if (event is PlayerLaunchEvent.Launch) onPlayStream(event.streamUrl)
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

private inline fun <reified T : ViewModel> vmFactory(
    crossinline create: () -> T,
): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
    override fun <VM : ViewModel> create(modelClass: KClass<VM>, extras: CreationExtras): VM {
        @Suppress("UNCHECKED_CAST")
        return create() as VM
    }
}
