package app.anime

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
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
import app.anime.ui.screens.TitleFacet
import app.anime.ui.tv.TvHomeScreen
import app.anime.ui.tv.TvScheduleScreen
import app.anime.ui.tv.TvSearchScreen
import java.net.URLDecoder
import java.net.URLEncoder
import kotlin.reflect.KClass

private object TvRoute {
    const val HOME     = "home"
    const val SEARCH   = "search"
    const val SETTINGS = "settings"
    const val SCHEDULE = "schedule"   // #8
    fun title(id: Int) = "title/$id"
    const val TITLE    = "title/{titleId}"
    fun facet(facet: TitleFacet) =
        "facet/${facet.kindValue()}/${encode(facet.routeValue())}/${encode(facet.title)}"
    const val FACET = "facet/{kind}/{value}/{label}"
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
                    onScheduleClick = { navController.navigate(TvRoute.SCHEDULE) },   // #8
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

            composable(
                route = TvRoute.FACET,
                arguments = listOf(
                    navArgument("kind") { type = NavType.StringType },
                    navArgument("value") { type = NavType.StringType },
                    navArgument("label") { type = NavType.StringType },
                ),
            ) { backStackEntry ->
                val kind = backStackEntry.arguments!!.getString("kind").orEmpty()
                val value = decode(backStackEntry.arguments!!.getString("value").orEmpty())
                val label = decode(backStackEntry.arguments!!.getString("label").orEmpty())
                val filters = facetFilters(kind, value, label)
                val vm: SearchViewModel = viewModel(
                    key = "facet_${kind}_${value}_${label}",
                    factory = remember(repo, kind, value, label) {
                        vmFactory {
                            SearchViewModel(
                                repo,
                                autoLoad = true,
                                initialFilters = filters,
                                initialFacetTitle = label,
                            )
                        }
                    },
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

            // #8: Schedule screen
            composable(TvRoute.SCHEDULE) {
                val vm: ScheduleViewModel = viewModel(
                    factory = remember(repo) { vmFactory { ScheduleViewModel(repo) } }
                )
                val state by vm.state.collectAsState()
                TvScheduleScreen(
                    state = state,
                    onTitleClick = { navController.navigate(TvRoute.title(it.titleId)) },
                    onRefresh = vm::refresh,
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
                val context = LocalContext.current

                // Back navigation fix: intercept the remote/system back button explicitly
                // so it always navigates back immediately, without focus-management interference.
                BackHandler(enabled = true) {
                    navController.popBackStack()
                }

                LaunchedEffect(vm) {
                    vm.playerEvent.collect { event ->
                        when (event) {
                            is PlayerLaunchEvent.Launch -> onPlayStream(event.streamUrl)
                            is PlayerLaunchEvent.OpenInBrowser -> {
                                // On Android TV, open web-player pages via system browser Intent
                                runCatching {
                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(event.url))
                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                    context.startActivity(intent)
                                }
                            }
                            else -> {}
                        }
                    }
                }

                val updateState by vm.updateState.collectAsState()
                TitleDetailScreen(
                    state = state,
                    updateState = updateState,
                    onBack = { navController.popBackStack() },
                    onEpisodePlay = vm::onEpisodeClick,
                    onEpisodeToggleWatched = { ep ->
                        vm.markEpisodeWatched(ep, ep.isWatched != true)
                    },
                    onToggleNeedToSee = vm::toggleNeedToSee,
                    onMarkAllWatched = { vm.markAllWatched(true) },
                    onUpdateFromProvider = { vm.updateFromProvider() },
                    onForceUpdateEpisodes = { vm.updateFromProvider(forceRefresh = true) },
                    onDismissUpdateResult = vm::dismissUpdateResult,
                    onPlayAll = vm::playAll,
                    onRelatedTitleClick = { relatedTitleId ->
                        navController.navigate(TvRoute.title(relatedTitleId))
                    },
                    onFacetClick = { facet ->
                        navController.navigate(TvRoute.facet(facet))
                    },
                )
            }
        }
    }
}

private fun TitleFacet.kindValue(): String =
    when {
        year != null -> "year"
        genre.isNotBlank() -> "genre"
        status.isNotBlank() -> "status"
        teamMemberId != null || teamMember.isNotBlank() -> "team"
        franchiseId != null -> "franchise"
        else -> "query"
    }

private fun TitleFacet.routeValue(): String =
    when (kindValue()) {
        "year" -> year?.toString().orEmpty()
        "genre" -> genre
        "status" -> status
        "team" -> teamMemberId?.toString() ?: teamMember
        "franchise" -> franchiseId?.toString().orEmpty()
        else -> title
    }

private fun facetFilters(kind: String, value: String, label: String): SearchFilters =
    when (kind) {
        "year" -> SearchFilters(year = value.toIntOrNull())
        "genre" -> SearchFilters(genre = value)
        "status" -> SearchFilters(status = value)
        "team" -> SearchFilters(teamMemberId = value.toIntOrNull(), teamMember = label.removePrefix("Команда: ").ifBlank { value })
        "franchise" -> SearchFilters(franchiseId = value.toIntOrNull(), franchise = label.removePrefix("Франшиза: ").ifBlank { value })
        else -> SearchFilters()
    }

private fun encode(value: String): String =
    URLEncoder.encode(value, Charsets.UTF_8.name())

private fun decode(value: String): String =
    URLDecoder.decode(value, Charsets.UTF_8.name())

private inline fun <reified T : ViewModel> vmFactory(
    crossinline create: () -> T,
): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
    override fun <VM : ViewModel> create(modelClass: KClass<VM>, extras: CreationExtras): VM {
        @Suppress("UNCHECKED_CAST")
        return create() as VM
    }
}
