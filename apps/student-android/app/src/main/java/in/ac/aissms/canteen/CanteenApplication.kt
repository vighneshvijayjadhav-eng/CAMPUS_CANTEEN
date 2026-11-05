package `in`.ac.aissms.canteen

import android.app.Application
import com.razorpay.Checkout
import `in`.ac.aissms.canteen.data.ApiClient
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.KeystoreTokenStorage

class CanteenApplication : Application() {
    lateinit var repository: CanteenRepository
        private set

    override fun onCreate() {
        super.onCreate()
        repository = CanteenRepository(ApiClient(BuildConfig.API_BASE_URL, KeystoreTokenStorage(this)))
        Checkout.preload(applicationContext)
    }
}
