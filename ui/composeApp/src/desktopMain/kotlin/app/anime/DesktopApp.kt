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
import java.net.URLDecoder
import java.net.URLEncoder
import kotlin.reflect.KClass

private object Route {
    const val SEARCH   = "search"   // catalog (auto-loads all titles)
    const val SETTINGS = "settings"
    const val SCHEDULE = "schedule" // #8
    const val ANIMEDIA_CATALOG = "animediaCatalog"
    fun title(id: Int) = "title/$id"
    const val TITLE    = "title/{titleId}"
    fun facet(facet: TitleFacet) =
        "facet/${facet.kindValue()}/${encode(facet.routeValue())}/${encode(facet.title)}"
    const val FACET = "facet/{kind}/{value}/{label}"
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
            var catalogRefreshToken by remember { mutableStateOf(0) }

            NavHost(navController = navController, startDestination = Route.SEARCH) {

                // ─── #7: Catalog / Browse (SearchScreen auto-loads all titles) ───
                composable(Route.SEARCH) {
                    val vm: SearchViewModel = viewModel(
                        factory = remember(repo) {
                            vmFactory { SearchViewModel(repo, autoLoad = true) }
                        }
                    )
                    val state by vm.state.collectAsState()
                    LaunchedEffect(catalogRefreshToken) {
                        if (catalogRefreshToken > 0) {
                            vm.retry()
                        }
                    }
                    SearchScreen(
                        state = state,
                        onQueryChange = vm::onQueryChange,
                        onFilterChange = vm::onFilterChange,   // #9
                        onToggleFilters = vm::toggleFiltersPanel,
                        onTitleClick = { navController.navigate(Route.title(it.titleId)) },
                        onLoadMore = vm::loadMore,
                        columns = 6,
                        onScheduleClick = { navController.navigate(Route.SCHEDULE) },
                        onAniMediaCatalogClick = { navController.navigate(Route.ANIMEDIA_CATALOG) },
                        onSettingsClick = { navController.navigate(Route.SETTINGS) },
                        onRandomAniLibertyClick = {
                            vm.loadRandomAniLiberty { titleId ->
                                catalogRefreshToken += 1
                                navController.navigate(Route.title(titleId))
                            }
                        },
                        onProviderLoad = { providerCode, providerQuery, byExternalId, limit ->
                            vm.loadFromProvider(
                                providerCode = providerCode,
                                providerQuery = providerQuery,
                                byExternalId = byExternalId,
                                limit = limit,
                            ) { titleId ->
                                catalogRefreshToken += 1
                                navController.navigate(Route.title(titleId))
                            }
                        },
                    )
                }

                composable(
                    route = Route.FACET,
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
                        }
                    )
                    val state by vm.state.collectAsState()
                    SearchScreen(
                        state = state,
                        onQueryChange = vm::onQueryChange,
                        onFilterChange = vm::onFilterChange,
                        onToggleFilters = vm::toggleFiltersPanel,
                        onTitleClick = { navController.navigate(Route.title(it.titleId)) },
                        onLoadMore = vm::loadMore,
                        columns = 6,
                        onScheduleClick = { navController.navigate(Route.SCHEDULE) },
                        onAniMediaCatalogClick = { navController.navigate(Route.ANIMEDIA_CATALOG) },
                        onSettingsClick = { navController.navigate(Route.SETTINGS) },
                        onRandomAniLibertyClick = {
                            vm.loadRandomAniLiberty { titleId ->
                                catalogRefreshToken += 1
                                navController.navigate(Route.title(titleId))
                            }
                        },
                        onProviderLoad = { providerCode, providerQuery, byExternalId, limit ->
                            vm.loadFromProvider(
                                providerCode = providerCode,
                                providerQuery = providerQuery,
                                byExternalId = byExternalId,
                                limit = limit,
                            ) { titleId ->
                                catalogRefreshToken += 1
                                navController.navigate(Route.title(titleId))
                            }
                        },
                    )
                }

                // ─── #8: Schedule ────────────────────────────────────────────────
                composable(Route.SCHEDULE) {
                    val vm: ScheduleViewModel = viewModel(
                        factory = remember(repo) { vmFactory { ScheduleViewModel(repo) } }
                    )
                    val state by vm.state.collectAsState()
                    ScheduleScreen(
                        state = state,
                        onTitleClick = { navController.navigate(Route.title(it.titleId)) },
                        onProviderItemLoad = { item ->
                            vm.loadProviderItem(item) { titleId ->
                                navController.navigate(Route.title(titleId))
                            }
                        },
                        onRefresh = vm::refresh,
                        onBack = { navController.popBackStack() },
                    )
                }

                // ─── Settings ────────────────────────────────────────────────────
                composable(Route.ANIMEDIA_CATALOG) {
                    val vm: AniMediaCatalogViewModel = viewModel(
                        factory = remember(repo) { vmFactory { AniMediaCatalogViewModel(repo) } }
                    )
                    val state by vm.state.collectAsState()
                    AniMediaCatalogScreen(
                        state = state,
                        onQueryChange = vm::onQueryChange,
                        onLoadedFilterChange = vm::onLoadedFilterChange,
                        onTitleClick = { navController.navigate(Route.title(it.titleId)) },
                        onProviderItemLoad = { item ->
                            vm.loadProviderItem(item) { titleId ->
                                catalogRefreshToken += 1
                                navController.navigate(Route.title(titleId))
                            }
                        },
                        onRefresh = vm::refresh,
                        onLoadMore = vm::loadMore,
                        onBack = { navController.popBackStack() },
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

                // ─── Title detail ─────────────────────────────────────────────────
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
                            when (event) {
                                is PlayerLaunchEvent.Launch ->
                                    launchPlayer(settings.playerCommand, event.streamUrl)
                                is PlayerLaunchEvent.OpenInBrowser ->
                                    launchBrowser(settings.browserCommand, event.url)
                                else -> {}
                            }
                        }
                    }

                    val updateState by vm.updateState.collectAsState()
                    TitleDetailScreen(
                        state = state,
                        updateState = updateState,
                        onBack = {
                            catalogRefreshToken += 1
                            navController.popBackStack()
                        },
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
                            navController.navigate(Route.title(relatedTitleId))
                        },
                        onFacetClick = { facet ->
                            navController.navigate(Route.facet(facet))
                        },
                    )
                }
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

// ---------------------------------------------------------------------------
// Browser launch — for web-player page URLs
// ---------------------------------------------------------------------------
private fun launchBrowser(browserCommand: String, url: String) {
    if (browserCommand.isNotBlank()) {
        // User-configured browser (e.g. "C:\Program Files\Google\Chrome\Application\chrome.exe")
        val parts = browserCommand.trim().split("\\s+".toRegex()) + url
        try {
            ProcessBuilder(parts).inheritIO().start()
            return
        } catch (_: Exception) { /* fall through to OS default */ }
    }
    // OS default browser
    try {
        val os = System.getProperty("os.name").lowercase()
        val cmd = when {
            os.contains("win") -> listOf("cmd", "/c", "start", "", url)
            os.contains("mac") -> listOf("open", url)
            else               -> listOf("xdg-open", url)
        }
        ProcessBuilder(cmd).start()
    } catch (_: Exception) { }
}
