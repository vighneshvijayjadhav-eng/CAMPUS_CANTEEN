package `in`.ac.aissms.canteen

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.razorpay.PaymentData
import com.razorpay.PaymentResultWithDataListener
import `in`.ac.aissms.canteen.payments.RazorpayCheckout
import `in`.ac.aissms.canteen.ui.CanteenApp
import `in`.ac.aissms.canteen.ui.theme.CanteenTheme

/** Single activity. Razorpay delivers checkout results to the activity, which forwards them. */
class MainActivity : ComponentActivity(), PaymentResultWithDataListener {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { CanteenTheme { CanteenApp() } }
    }

    override fun onPaymentSuccess(razorpayPaymentId: String?, data: PaymentData?) {
        RazorpayCheckout.onSuccess(data)
    }

    override fun onPaymentError(code: Int, response: String?, data: PaymentData?) {
        RazorpayCheckout.onError(code, response)
    }
}
