package `in`.ac.aissms.canteen.data

import kotlinx.serialization.Serializable

/** API models. Field names map to the backend's snake_case JSON via the shared Json config. */

@Serializable
data class TokenResponse(
    val accessToken: String,
    val refreshToken: String,
    val sessionId: String,
)

@Serializable
data class Me(
    val id: String,
    val email: String,
    val displayName: String,
    val avatarUrl: String? = null,
    val selectedInstituteId: String? = null,
)

@Serializable
data class Institute(val id: String, val slug: String, val name: String)

@Serializable
data class CanteenSummary(
    val id: String,
    val slug: String,
    val name: String,
    val operating: Boolean = false,
    val acceptingOrders: Boolean = false,
)

@Serializable
data class MenuVariant(
    val id: String,
    val label: String,
    val pricePaise: Int? = null,
    val verified: Boolean = false,
    val available: Boolean = false,
) {
    val orderable: Boolean get() = verified && available && pricePaise != null
}

@Serializable
data class MenuItem(
    val id: String,
    val name: String,
    val category: String,
    val variants: List<MenuVariant> = emptyList(),
)

@Serializable
data class CartLine(
    val variantId: String,
    val itemName: String,
    val variant: String,
    val quantity: Int,
    val unitPricePaise: Int? = null,
    val lineTotalPaise: Int? = null,
    val orderable: Boolean = false,
)

@Serializable
data class Cart(
    val canteenId: String? = null,
    val lines: List<CartLine> = emptyList(),
    val totalPaise: Int = 0,
) {
    val itemCount: Int get() = lines.sumOf { it.quantity }
    val allOrderable: Boolean get() = lines.isNotEmpty() && lines.all { it.orderable }
}

@Serializable
data class OrderSummary(
    val id: String,
    val canteenId: String,
    val canteenName: String? = null,
    val state: String,
    val stateLabel: String,
    val totalPaise: Int,
    val createdAt: String,
    val refundStatus: String? = null,
    val exceptionStatus: String? = null,
)

@Serializable
data class StationRemaining(val station: String, val remaining: Int)

@Serializable
data class OrderLine(
    val id: String,
    val name: String,
    val variant: String,
    val station: String,
    val unitPricePaise: Int,
    val quantity: Int,
    val lineTotalPaise: Int,
    val fulfilled: Int,
    val remaining: Int,
)

@Serializable
data class PaymentSummary(
    val status: String,
    val providerPaymentId: String? = null,
    val amountPaise: Int,
    val failureReason: String? = null,
)

@Serializable
data class RefundInfo(
    val id: String,
    val amountPaise: Int,
    val reason: String,
    val status: String,
)

@Serializable
data class OrderDetail(
    val id: String,
    val canteenId: String,
    val canteenName: String? = null,
    val state: String,
    val stateLabel: String,
    val totalPaise: Int,
    val createdAt: String,
    val paymentVerifiedAt: String? = null,
    val refundStatus: String? = null,
    val exceptionStatus: String? = null,
    val pickupCode: String? = null,
    val remainingByStation: List<StationRemaining> = emptyList(),
    val lines: List<OrderLine> = emptyList(),
    val payment: PaymentSummary? = null,
    val refunds: List<RefundInfo> = emptyList(),
)

@Serializable
data class PaymentParams(
    val orderId: String,
    val provider: String,
    val keyId: String,
    val providerOrderId: String,
    val amountPaise: Int,
    val currency: String,
    val merchantName: String,
    val mode: String,
)

@Serializable
data class PaymentConfirmation(val paymentStatus: String, val order: OrderDetail)
