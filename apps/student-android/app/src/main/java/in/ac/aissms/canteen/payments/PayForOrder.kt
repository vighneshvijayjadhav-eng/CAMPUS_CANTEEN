package `in`.ac.aissms.canteen.payments

import android.app.Activity
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.friendlyError

/**
 * Opens Razorpay Checkout for an unpaid order and reports the result to the server. Returns a
 * message for the student, or null when the server confirmed the payment. The order is only
 * ever marked paid by the server (callback verification, webhook or reconciliation).
 */
suspend fun payForOrder(repo: CanteenRepository, activity: Activity, orderId: String): String? {
    val params = runCatching { repo.startPayment(orderId) }.getOrElse { return friendlyError(it) }
    val email = runCatching { repo.me().email }.getOrNull()
    return when (val outcome = RazorpayCheckout.pay(activity, params, email)) {
        is PaymentOutcome.Failed ->
            if (outcome.code == com.razorpay.Checkout.PAYMENT_CANCELED) {
                "Payment cancelled. Your order is saved – you can pay from the order screen."
            } else {
                "Payment didn't go through. You can try again from the order screen."
            }
        is PaymentOutcome.Completed -> runCatching {
            repo.confirmPayment(orderId, outcome.providerOrderId, outcome.paymentId, outcome.signature)
        }.fold(
            { if (it.paymentStatus == "CAPTURED") null else "Payment is being confirmed. This page updates automatically." },
            { "We're confirming your payment with the bank. This page updates automatically." },
        )
    }
}
