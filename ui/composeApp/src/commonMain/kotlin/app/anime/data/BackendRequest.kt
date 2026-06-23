package app.anime.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*

/** Serialisable wrapper for the JSON-tool protocol. */
@Serializable
data class BackendRequest(
    val op: String,
    val params: JsonObject,
)

/** Serialisable envelope of every backend response. */
@Serializable
data class BackendResponse(
    val ok: Boolean,
    val result: JsonObject? = null,
    val error: String? = null,
)

// ---------------------------------------------------------------------------
// Helper builders
// ---------------------------------------------------------------------------

internal fun buildRequest(op: String, params: Map<String, Any?>): BackendRequest {
    val json = buildJsonObject {
        for ((k, v) in params) {
            when (v) {
                null           -> put(k, JsonNull)
                is Boolean     -> put(k, v)
                is Int         -> put(k, v)
                is Long        -> put(k, v)
                is Double      -> put(k, v)
                is Float       -> put(k, v)
                is String      -> put(k, v)
                is List<*>     -> put(k, buildJsonArray {
                    v.forEach { item ->
                        when (item) {
                            is Int    -> add(item)
                            is Long   -> add(item)
                            is String -> add(item)
                            else      -> add(item.toString())
                        }
                    }
                })
                else           -> put(k, v.toString())
            }
        }
    }
    return BackendRequest(op = op, params = json)
}
