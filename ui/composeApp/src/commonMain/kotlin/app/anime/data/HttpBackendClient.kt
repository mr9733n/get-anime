package app.anime.data

import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.request.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*
import kotlinx.serialization.json.*

/**
 * HTTP backend client — used on ALL platforms.
 *
 * Desktop connects to http://localhost:8765  (backend running on same machine)
 * Android TV connects to http://192.168.x.x:8765  (backend on LAN)
 *
 * The Ktor engine is injected:
 *   Desktop  → CIO (desktopMain actual)
 *   Android  → OkHttp (androidMain actual)
 */
class HttpBackendClient(
    override val baseUrl: String,
) : BackendClient {

    private val jsonInstance = Json { ignoreUnknownKeys = true }

    private val httpClient = HttpClient(createHttpClientEngine()) {
        install(HttpTimeout) {
            requestTimeoutMillis = 300_000L
            socketTimeoutMillis = 300_000L
            connectTimeoutMillis = 30_000L
        }
        install(ContentNegotiation) {
            json(jsonInstance)
        }
    }

    override suspend fun call(op: String, params: Map<String, Any?>): JsonObject {
        val request = buildRequest(op, params)
        val response: BackendResponse = httpClient.post("$baseUrl/api") {
            contentType(ContentType.Application.Json)
            setBody(request)
        }.body()

        if (!response.ok) {
            throw BackendException(response.error ?: "Backend error (op=$op)", op)
        }
        return response.result ?: buildJsonObject { }
    }

    override fun close() {
        httpClient.close()
    }
}

/** Platform-specific Ktor engine factory. */
expect fun createHttpClientEngine(): io.ktor.client.engine.HttpClientEngine
