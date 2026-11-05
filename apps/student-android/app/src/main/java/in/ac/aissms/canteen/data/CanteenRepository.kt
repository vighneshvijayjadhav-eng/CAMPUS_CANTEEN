package `in`.ac.aissms.canteen.data

import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** All backend calls the student app makes. The server is the source of truth for every
 *  price, total, availability and order state; nothing here computes money. */
class CanteenRepository(private val api: ApiClient) {
    val signedIn = api.signedIn

    suspend fun signInWithGoogle(idToken: String, deviceName: String) {
        val body = buildJsonObject {
            put("id_token", idToken)
            put("device_name", deviceName.take(120))
        }
        api.startSession(
            api.send("POST", "/api/v1/auth/google", body, TokenResponse.serializer(), authenticated = false),
        )
    }

    /** Revokes this device's session on the server (best effort), then forgets it locally. */
    suspend fun signOut() {
        val sessionId = api.currentSessionId()
        if (sessionId != null) {
            runCatching {
                api.send(
                    "POST",
                    "/api/v1/student/sessions/revoke",
                    buildJsonObject { put("session_id", sessionId) },
                    JsonObject.serializer(),
                )
            }
        }
        api.endSession()
    }

    suspend fun me(): Me = api.get("/api/v1/student/me", Me.serializer())

    suspend fun institutes(): List<Institute> =
        api.get("/api/v1/institutes", ListSerializer(Institute.serializer()))

    suspend fun selectInstitute(instituteId: String) {
        api.send(
            "PATCH",
            "/api/v1/student/preferences/institute",
            buildJsonObject { put("institute_id", instituteId) },
            JsonObject.serializer(),
        )
    }

    suspend fun canteens(instituteId: String): List<CanteenSummary> =
        api.get("/api/v1/institutes/$instituteId/canteens", ListSerializer(CanteenSummary.serializer()))

    suspend fun menu(canteenId: String): List<MenuItem> =
        api.get("/api/v1/canteens/$canteenId/menu", ListSerializer(MenuItem.serializer()))

    suspend fun cart(): Cart = api.get("/api/v1/student/cart", Cart.serializer())

    suspend fun setCartQuantity(variantId: String, quantity: Int): Cart = api.send(
        "PUT",
        "/api/v1/student/cart/lines/$variantId",
        buildJsonObject { put("quantity", quantity) },
        Cart.serializer(),
    )

    suspend fun clearCart(): Cart = api.send("DELETE", "/api/v1/student/cart", null, Cart.serializer())

    /** [requestId] must be reused when retrying the same tap so a retry cannot double-order. */
    suspend fun checkout(requestId: String, expectedTotalPaise: Int): OrderDetail = api.send(
        "POST",
        "/api/v1/student/checkout",
        buildJsonObject {
            put("request_id", requestId)
            put("expected_total_paise", expectedTotalPaise)
        },
        OrderDetail.serializer(),
    )

    suspend fun startPayment(orderId: String): PaymentParams =
        api.send("POST", "/api/v1/student/orders/$orderId/payment", null, PaymentParams.serializer())

    suspend fun confirmPayment(
        orderId: String,
        providerOrderId: String,
        providerPaymentId: String,
        signature: String,
    ): PaymentConfirmation = api.send(
        "POST",
        "/api/v1/student/orders/$orderId/payment/confirm",
        buildJsonObject {
            put("provider_order_id", providerOrderId)
            put("provider_payment_id", providerPaymentId)
            put("signature", signature)
        },
        PaymentConfirmation.serializer(),
    )

    suspend fun orders(): List<OrderSummary> =
        api.get("/api/v1/student/orders", ListSerializer(OrderSummary.serializer()))

    suspend fun order(orderId: String): OrderDetail =
        api.get("/api/v1/student/orders/$orderId", OrderDetail.serializer())

    suspend fun cancelOrder(orderId: String): OrderDetail =
        api.send("POST", "/api/v1/student/orders/$orderId/cancel", null, OrderDetail.serializer())
}
