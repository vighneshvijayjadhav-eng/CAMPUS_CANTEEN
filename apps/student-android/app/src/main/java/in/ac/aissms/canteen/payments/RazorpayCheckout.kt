package `in`.ac.aissms.canteen.payments

import android.app.Activity
import com.razorpay.Checkout
import com.razorpay.PaymentData
import `in`.ac.aissms.canteen.data.PaymentParams
import kotlinx.coroutines.CompletableDeferred
import org.json.JSONObject

sealed interface PaymentOutcome {
    /** Razorpay says the student completed checkout. Still unverified: the server decides. */
    data class Completed(val providerOrderId: String, val paymentId: String, val signature: String) :
        PaymentOutcome

    data class Failed(val code: Int, val description: String?) : PaymentOutcome
}

/**
 * Bridges Razorpay's Activity callbacks (MainActivity implements PaymentResultWithDataListener)
 * into a suspend call. Only one checkout can be open at a time.
 */
object RazorpayCheckout {
    private var pending: CompletableDeferred<PaymentOutcome>? = null

    suspend fun pay(activity: Activity, params: PaymentParams, email: String?): PaymentOutcome {
        val result = CompletableDeferred<PaymentOutcome>()
        pending?.cancel()
        pending = result
        val options = JSONObject().apply {
            put("name", params.merchantName)
            put("description", "Canteen order")
            put("order_id", params.providerOrderId)
            put("amount", params.amountPaise)
            put("currency", params.currency)
            if (email != null) put("prefill", JSONObject().put("email", email))
            put("theme", JSONObject().put("color", "#1E5BD8"))
        }
        Checkout().apply { setKeyID(params.keyId) }.open(activity, options)
        return result.await()
    }

    fun onSuccess(data: PaymentData?) {
        val outcome = if (data?.orderId != null && data.paymentId != null && data.signature != null) {
            PaymentOutcome.Completed(data.orderId, data.paymentId, data.signature)
        } else {
            PaymentOutcome.Failed(-1, "Incomplete payment response")
        }
        pending?.complete(outcome)
        pending = null
    }

    fun onError(code: Int, description: String?) {
        pending?.complete(PaymentOutcome.Failed(code, description))
        pending = null
    }
}
