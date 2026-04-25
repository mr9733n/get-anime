package app.anime

import app.anime.data.BackendClient
import app.anime.data.BackendException
import app.anime.data.BackendRequest
import app.anime.data.BackendResponse
import app.anime.data.buildRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*

/**
 * Desktop backend client: spawns backend_tool(.exe) and communicates
 * via one JSON line per call on stdin/stdout.
 *
 * One process per call (one-shot mode) — simple and safe.
 * If you need speed, switch to persistent-process mode with a read loop.
 */
class SubprocessBackendClient(
    private val backendToolPath: String,
    private val dbPath: String,
    private val extraArgs: List<String> = emptyList(),
) : BackendClient {

    private val json = Json { ignoreUnknownKeys = true }

    override suspend fun call(op: String, params: Map<String, Any?>): JsonObject =
        withContext(Dispatchers.IO) {
            val request = buildRequest(op, params)
            val requestLine = json.encodeToString(request)

            val command = buildList {
                add(backendToolPath)
                add("--db"); add(dbPath)
                addAll(extraArgs)
            }

            val process = ProcessBuilder(command)
                .redirectErrorStream(false)
                .start()

            try {
                // Write request
                process.outputStream.bufferedWriter().use { it.write(requestLine + "\n") }

                // Read response (one line)
                val responseLine = process.inputStream.bufferedReader().readLine()
                    ?: throw BackendException("Backend returned empty response", op)

                process.waitFor()

                val envelope: BackendResponse = json.decodeFromString(responseLine)
                if (!envelope.ok) {
                    throw BackendException(envelope.error ?: "Backend error", op)
                }
                envelope.result ?: buildJsonObject { }
            } finally {
                process.destroyForcibly()
            }
        }

    override fun close() { /* one-shot mode, nothing to close */ }
}

/**
 * Helper: find backend_tool next to the running jar / in working dir.
 */
fun resolveBackendTool(): String {
    val isWindows = System.getProperty("os.name").lowercase().contains("win")
    val ext = if (isWindows) ".exe" else ""
    val candidates = listOf(
        // next to the installed app binary
        java.io.File(System.getProperty("compose.application.resources.dir", "."))
            .resolve("backend_tool$ext").absolutePath,
        // dev: project root (running from IDE)
        java.io.File("..").resolve("dist/backend_tool/backend_tool$ext").absolutePath,
        // fallback: python module run
        if (isWindows) "python" else "python3",
    )
    for (c in candidates) {
        if (java.io.File(c).exists()) return c
    }
    // Last resort: run as python module
    return if (isWindows) "python" else "python3"
}

/**
 * Build a SubprocessBackendClient that uses either the compiled binary
 * or falls back to `python -m backend.transport.json_tool.backend_tool`.
 */
fun createDesktopBackendClient(dbPath: String): BackendClient {
    val isWindows = System.getProperty("os.name").lowercase().contains("win")
    val ext = if (isWindows) ".exe" else ""

    // Try compiled binary first
    val binaryPath = java.io.File("dist/backend_tool/backend_tool$ext").absolutePath
    return if (java.io.File(binaryPath).exists()) {
        SubprocessBackendClient(backendToolPath = binaryPath, dbPath = dbPath)
    } else {
        // Dev mode: use python module
        val python = if (isWindows) "python" else "python3"
        SubprocessBackendClient(
            backendToolPath = python,
            dbPath = dbPath,
            extraArgs = listOf("-m", "backend.transport.json_tool.backend_tool", "--db", dbPath),
        )
    }
}
