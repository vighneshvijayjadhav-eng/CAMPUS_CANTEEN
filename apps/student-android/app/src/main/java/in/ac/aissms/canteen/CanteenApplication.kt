package `in`.ac.aissms.canteen

import android.app.Application
import `in`.ac.aissms.canteen.data.ApiClient
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.KeystoreTokenStorage

class CanteenApplication : Application() {
    lateinit var repository: CanteenRepository
        private set

    override fun onCreate() {
        super.onCreate()
        // No Razorpay Checkout.preload() here: it initializes a WebView on the main thread and
        // froze startup (ANR) on a slow device. Checkout initializes itself when it opens.
        repository = CanteenRepository(ApiClient(BuildConfig.API_BASE_URL, KeystoreTokenStorage(this)))
    }
}
