package `in`.ac.aissms.canteen.data

import java.time.Duration
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** ₹40 for whole rupees, ₹40.50 otherwise. Amounts are always integer paise from the server. */
fun rupees(paise: Int): String {
    val whole = paise / 100
    val fraction = paise % 100
    return if (fraction == 0) "₹$whole" else "₹$whole.${fraction.toString().padStart(2, '0')}"
}

fun parseInstant(value: String?): Instant? =
    value?.let { runCatching { OffsetDateTime.parse(it).toInstant() }.getOrNull() }

private val IST: ZoneId = ZoneId.of("Asia/Kolkata")
private val ORDER_TIME = DateTimeFormatter.ofPattern("d MMM, h:mm a", Locale.ENGLISH)

fun orderTime(value: String): String =
    parseInstant(value)?.atZone(IST)?.format(ORDER_TIME) ?: ""

const val CANCEL_WINDOW_SECONDS = 5 * 60L

/**
 * Seconds left to self-cancel, for display only; the server clock decides. Null when the
 * order is not cancellable by the student.
 */
fun cancelSecondsLeft(order: OrderDetail, now: Instant): Long? {
    if (order.state != "PAID_ACTIVE") return null
    if (order.lines.any { it.fulfilled > 0 }) return null
    val paidAt = parseInstant(order.paymentVerifiedAt) ?: return null
    val left = CANCEL_WINDOW_SECONDS - Duration.between(paidAt, now).seconds
    return left.takeIf { it > 0 }
}

fun countdown(seconds: Long): String = "%d:%02d".format(seconds / 60, seconds % 60)

fun isActive(state: String) = state in setOf("PAYMENT_PENDING", "PAID_ACTIVE", "PARTIALLY_COLLECTED")

fun refundLabel(status: String?): String? = when (status) {
    "REQUESTED" -> "Refund requested"
    "PENDING" -> "Refund in progress"
    "REFUNDED" -> "Refunded"
    "FAILED" -> "Refund failed – the canteen will contact you"
    else -> null
}

/** Student-facing text for backend error codes. */
fun friendlyError(error: Throwable): String = when ((error as? ApiException)?.code) {
    "NETWORK_ERROR" -> "Can't reach the canteen server. Check your connection and try again."
    "AUTHENTICATION_REQUIRED" -> "Your session has ended. Please sign in again."
    "CART_CANTEEN_CONFLICT" -> "Your cart has items from another canteen."
    "MENU_VARIANT_UNAVAILABLE", "CART_ITEM_UNAVAILABLE" ->
        "An item in your cart is no longer available. Please review your cart."
    "PRICE_CHANGED" -> "Prices changed since you opened your cart. Please check the new total."
    "CART_EMPTY" -> "Your cart is empty."
    "CANTEEN_CLOSED", "CANTEEN_NOT_OPERATING" -> "This canteen isn't taking orders right now."
    "CANTEEN_NOT_APPROVED" -> "This canteen isn't available for ordering yet."
    "PAYMENTS_NOT_CONFIGURED" -> "Online payment isn't set up for this canteen yet."
    "PAYMENT_PROVIDER_UNAVAILABLE", "PAYMENT_PROVIDER_REJECTED" ->
        "The payment service is unavailable. Please try again shortly."
    "PAYMENT_SIGNATURE_INVALID" -> "We couldn't verify that payment. If money was deducted it will be refunded."
    "CANCELLATION_WINDOW_CLOSED" -> "The 5-minute cancellation window has passed."
    "ORDER_NOT_CANCELLABLE" -> "This order can no longer be cancelled."
    "ORDER_NOT_PAYABLE" -> "This order no longer needs payment."
    "GOOGLE_ACCOUNT_CONFLICT" -> "This Google account can't be used. Try a different account."
    "RATE_LIMITED" -> "Too many attempts. Please wait a minute and try again."
    "REVIEW_REQUIRES_COLLECTION" -> "You can review an item once you've collected it."
    "REVIEW_EXISTS" -> "You've already reviewed this item from this order."
    "REVIEW_REMOVED" -> "This review was removed by the canteen and can't be edited."
    "TOO_MANY_PHOTOS" -> "You can add up to 3 photos."
    "INVALID_IMAGE" -> "That file isn't a supported photo. Use a JPEG, PNG or WebP image."
    "IMAGE_TOO_LARGE" -> "That photo is too large. Try a smaller one."
    "ALREADY_REPORTED" -> "You've already reported this review."
    "REPORT_REQUIRES_PURCHASE" -> "Only students who have collected food here can report reviews."
    "CANNOT_REPORT_OWN_REVIEW" -> "You can't report your own review."
    else -> "Something went wrong. Please try again."
}
