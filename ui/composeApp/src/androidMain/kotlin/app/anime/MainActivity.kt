package app.anime

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import app.anime.data.AndroidAppSettings
import app.anime.data.AnimeRepository
import app.anime.data.HttpBackendClient
import app.anime.data.createAppSettings
import coil3.ImageLoader
import coil3.SingletonImageLoader
import coil3.network.ktor3.KtorNetworkFetcherFactory

class MainActivity : ComponentActivity() {

    private lateinit var repo: AnimeRepository
    private var backendClient: HttpBackendClient? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Initialize Coil3 with Ktor network fetcher (uses OkHttp engine already in deps)
        SingletonImageLoader.setSafe { context ->
            ImageLoader.Builder(context)
                .components { add(KtorNetworkFetcherFactory()) }
                .build()
        }

        // Must init before createAppSettings() is called anywhere
        AndroidAppSettings.init(this)
        val settings = createAppSettings()

        backendClient = HttpBackendClient(settings.backendUrl)
        repo = AnimeRepository(backendClient!!)

        setContent {
            TvApp(
                repo = repo,
                settings = settings,
                onPlayStream = { url -> launchVideoPlayer(url) },
                onBackendUrlChange = { newUrl ->
                    // Recreate client with new URL
                    backendClient?.close()
                    backendClient = HttpBackendClient(newUrl)
                    repo = AnimeRepository(backendClient!!)
                },
            )
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        backendClient?.close()
    }

    private fun launchVideoPlayer(url: String) {
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(Uri.parse(url), "video/*")
        }
        startActivity(Intent.createChooser(intent, "Выберите плеер"))
    }
}
