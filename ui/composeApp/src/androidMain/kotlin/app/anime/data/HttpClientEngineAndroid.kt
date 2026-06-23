package app.anime.data

import io.ktor.client.engine.*
import io.ktor.client.engine.okhttp.*

actual fun createHttpClientEngine(): HttpClientEngine = OkHttp.create()
