package app.anime.data

import kotlinx.serialization.json.JsonObject

/**
 * Contract for communicating with the Python backend.
 *
 * On Desktop  → SubprocessBackendClient (stdin/stdout IPC)
 * On Android  → HttpBackendClient (HTTP to local/remote backend server)
 *
 * Every call maps to:
 *   request:  {"op": "titles.search", "params": {...}}
 *   response: {"ok": true, "result": {...}, "error": null}
 */
interface BackendClient {
    /**
     * Execute a backend operation.
     * @param op   e.g. "titles.search"
     * @param params raw JSON-serialisable map
     * @return parsed result object from response["result"]
     * @throws BackendException if ok == false or transport error
     */
    suspend fun call(op: String, params: Map<String, Any?> = emptyMap()): JsonObject

    /** Release resources (close subprocess / HTTP client). */
    fun close()
}

class BackendException(message: String, val op: String? = null) : Exception(message)
