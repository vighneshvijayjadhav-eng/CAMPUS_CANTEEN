package `in`.ac.aissms.canteen.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNamingStrategy
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

/** A backend error code (e.g. PRICE_CHANGED) or NETWORK_ERROR when the API is unreachable. */
class ApiException(val status: Int, val code: String) : Exception(code)

@OptIn(ExperimentalSerializationApi::class)
val ApiJson = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
    namingStrategy = JsonNamingStrategy.SnakeCase
}

/**
 * Thin HTTP client. Adds the bearer token, refreshes the rotating session once on 401 (one
 * refresh at a time across concurrent calls), and signals sign-out when refresh is rejected.
 */
class ApiClient(
    private val baseUrl: String,
    private val tokens: TokenStorage,
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build(),
) {
    private val refreshLock = Mutex()
    private val _signedIn = MutableStateFlow(tokens.load() != null)
    val signedIn: StateFlow<Boolean> = _signedIn

    fun startSession(response: TokenResponse) {
        tokens.save(StoredSession(response.accessToken, response.refreshToken, response.sessionId))
        _signedIn.value = true
    }

    fun endSession() {
        tokens.clear()
        _signedIn.value = false
    }

    fun currentSessionId(): String? = tokens.load()?.sessionId

    suspend fun <T> get(path: String, strategy: DeserializationStrategy<T>): T =
        call("GET", path, null, strategy, authenticated = true)

    suspend fun <T> send(
        method: String,
        path: String,
        body: JsonElement?,
        strategy: DeserializationStrategy<T>,
        authenticated: Boolean = true,
    ): T = call(method, path, body, strategy, authenticated)

    private suspend fun <T> call(
        method: String,
        path: String,
        body: JsonElement?,
        strategy: DeserializationStrategy<T>,
        authenticated: Boolean,
    ): T {
        val used = if (authenticated) tokens.load() ?: throw signedOut() else null
        var response = execute(method, path, body, used?.accessToken)
        if (response.status == 401 && used != null) {
            refresh(used)
            val renewed = tokens.load() ?: throw signedOut()
            response = execute(method, path, body, renewed.accessToken)
            if (response.status == 401) {
                endSession()
                throw ApiException(401, "AUTHENTICATION_REQUIRED")
            }
        }
        if (response.status !in 200..299) throw ApiException(response.status, errorCode(response))
        return ApiJson.decodeFromString(strategy, response.body)
    }

    private suspend fun refresh(used: StoredSession) = refreshLock.withLock {
        val current = tokens.load() ?: throw signedOut()
        if (current.accessToken != used.accessToken) return@withLock // another call refreshed
        val payload = buildJsonObject { put("refresh_token", current.refreshToken) }
        val response = execute("POST", "/api/v1/auth/student/refresh", payload, null)
        if (response.status in 200..299) {
            startSession(ApiJson.decodeFromString(TokenResponse.serializer(), response.body))
        } else if (response.status in 400..499 && response.status != 429) {
            endSession()
            throw ApiException(401, "AUTHENTICATION_REQUIRED")
        } else {
            throw ApiException(response.status, errorCode(response))
        }
    }

    private fun signedOut(): ApiException {
        _signedIn.value = false
        return ApiException(401, "AUTHENTICATION_REQUIRED")
    }

    private data class RawResponse(val status: Int, val body: String)

    private suspend fun execute(method: String, path: String, body: JsonElement?, token: String?) =
        withContext(Dispatchers.IO) {
            val requestBody = body?.toString()?.toRequestBody(JSON_TYPE)
                ?: if (method == "POST" || method == "PUT") ByteArray(0).toRequestBody(null) else null
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + path)
                .method(method, requestBody)
                .header("Accept", "application/json")
                .apply { if (token != null) header("Authorization", "Bearer $token") }
                .build()
            try {
                http.newCall(request).execute().use { RawResponse(it.code, it.body?.string().orEmpty()) }
            } catch (error: IOException) {
                throw ApiException(0, "NETWORK_ERROR")
            }
        }

    private fun errorCode(response: RawResponse): String = runCatching {
        val json = ApiJson.parseToJsonElement(response.body) as JsonObject
        json["error"]?.jsonPrimitive?.content ?: if ("detail" in json) "VALIDATION_ERROR" else null
    }.getOrNull() ?: "HTTP_${response.status}"

    private companion object {
        val JSON_TYPE = "application/json".toMediaType()
    }
}
