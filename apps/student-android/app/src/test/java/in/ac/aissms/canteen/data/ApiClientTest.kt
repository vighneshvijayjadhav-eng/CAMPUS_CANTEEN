package `in`.ac.aissms.canteen.data

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class ApiClientTest {
    private val server = MockWebServer()
    private val refreshes = AtomicInteger()
    private var refreshStatus = 200

    @Before
    fun start() {
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when (request.path) {
                "/api/v1/auth/student/refresh" -> {
                    refreshes.incrementAndGet()
                    if (refreshStatus != 200) {
                        MockResponse().setResponseCode(refreshStatus).setBody("""{"error":"AUTHENTICATION_REQUIRED"}""")
                    } else {
                        MockResponse().setBody(
                            """{"access_token":"new-access","refresh_token":"new-refresh","session_id":"s1","token_type":"Bearer"}""",
                        )
                    }
                }
                "/api/v1/student/cart" ->
                    if (request.getHeader("Authorization") == "Bearer new-access") {
                        MockResponse().setBody("""{"canteen_id":"coe","lines":[],"total_paise":0,"extra":1}""")
                    } else {
                        MockResponse().setResponseCode(401).setBody("""{"error":"AUTHENTICATION_REQUIRED"}""")
                    }
                "/api/v1/student/checkout" ->
                    MockResponse().setResponseCode(409).setBody("""{"error":"PRICE_CHANGED"}""")
                "/api/v1/student/orders/x/payment" ->
                    MockResponse().setResponseCode(422).setBody("""{"detail":[{"msg":"bad"}]}""")
                else -> MockResponse().setResponseCode(404)
            }
        }
        server.start()
    }

    @After
    fun stop() = server.shutdown()

    private fun client(storage: TokenStorage) = ApiClient(server.url("/").toString(), storage)

    private fun storage() = InMemoryTokenStorage(StoredSession("old-access", "old-refresh", "s1"))

    @Test
    fun expiredAccessTokenIsRefreshedOnceAndRetried() = runBlocking {
        val tokens = storage()
        val api = client(tokens)
        val cart = api.get("/api/v1/student/cart", Cart.serializer())
        assertEquals("coe", cart.canteenId)
        assertEquals(StoredSession("new-access", "new-refresh", "s1"), tokens.load())
        assertEquals(1, refreshes.get())
        assertTrue(api.signedIn.value)
    }

    @Test
    fun concurrentCallsShareOneRefresh() = runBlocking {
        val api = client(storage())
        (1..5).map { async { api.get("/api/v1/student/cart", Cart.serializer()) } }.awaitAll()
        assertEquals(1, refreshes.get())
    }

    @Test
    fun rejectedRefreshSignsOut() = runBlocking {
        refreshStatus = 401
        val tokens = storage()
        val api = client(tokens)
        try {
            api.get("/api/v1/student/cart", Cart.serializer())
            fail("expected sign-out")
        } catch (error: ApiException) {
            assertEquals("AUTHENTICATION_REQUIRED", error.code)
        }
        assertNull(tokens.load())
        assertFalse(api.signedIn.value)
    }

    @Test
    fun rateLimitedRefreshKeepsTheSession() = runBlocking {
        refreshStatus = 429
        val tokens = storage()
        try {
            client(tokens).get("/api/v1/student/cart", Cart.serializer())
            fail("expected error")
        } catch (error: ApiException) {
            assertEquals(429, error.status)
        }
        assertEquals("old-refresh", tokens.load()?.refreshToken)
    }

    @Test
    fun backendErrorCodesAreSurfaced() = runBlocking {
        val api = client(storage())
        val price = runCatching {
            api.send("POST", "/api/v1/student/checkout", null, OrderDetail.serializer())
        }.exceptionOrNull() as ApiException
        assertEquals("PRICE_CHANGED", price.code)
        val validation = runCatching {
            api.send("POST", "/api/v1/student/orders/x/payment", null, PaymentParams.serializer())
        }.exceptionOrNull() as ApiException
        assertEquals("VALIDATION_ERROR", validation.code)
    }

    @Test
    fun signedOutCallsFailWithoutNetwork() = runBlocking {
        val api = client(InMemoryTokenStorage())
        val error = runCatching { api.get("/api/v1/student/cart", Cart.serializer()) }.exceptionOrNull()
        assertEquals("AUTHENTICATION_REQUIRED", (error as ApiException).code)
        assertEquals(0, server.requestCount)
    }

    @Test
    fun unreachableServerIsANetworkError() = runBlocking {
        val api = ApiClient("http://127.0.0.1:1", storage())
        val error = runCatching { api.get("/api/v1/student/cart", Cart.serializer()) }.exceptionOrNull()
        assertEquals("NETWORK_ERROR", (error as ApiException).code)
    }
}
