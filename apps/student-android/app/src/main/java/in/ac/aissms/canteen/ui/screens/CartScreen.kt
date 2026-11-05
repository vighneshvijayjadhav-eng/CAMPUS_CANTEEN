package `in`.ac.aissms.canteen.ui.screens

import android.app.Activity
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.ac.aissms.canteen.data.ApiException
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.Cart
import `in`.ac.aissms.canteen.data.CartLine
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.data.rupees
import `in`.ac.aissms.canteen.payments.payForOrder
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.Message
import `in`.ac.aissms.canteen.ui.QuantityStepper
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.theme.DangerRed
import `in`.ac.aissms.canteen.ui.theme.Muted
import `in`.ac.aissms.canteen.ui.theme.PayGreen
import kotlinx.coroutines.launch
import java.util.UUID

class CartViewModel(private val repo: CanteenRepository) : ViewModel() {
    var state by mutableStateOf<Load<Cart>>(Load.Loading)
        private set
    var busy by mutableStateOf(false)
        private set
    var message by mutableStateOf<String?>(null)
    var placedOrderId by mutableStateOf<String?>(null)

    // One id per confirmed total: a retried tap returns the same order instead of a new one.
    private var checkoutKey: Pair<Int, String>? = null

    init { load() }

    fun load() {
        viewModelScope.launch {
            state = runCatching { repo.cart() }.fold({ Load.Ready(it) }, { Load.Failed(friendlyError(it)) })
        }
    }

    fun setQuantity(line: CartLine, quantity: Int) {
        if (busy) return
        busy = true
        viewModelScope.launch {
            runCatching { repo.setCartQuantity(line.variantId, quantity) }
                .onSuccess { state = Load.Ready(it) }
                .onFailure { message = friendlyError(it); load() }
            busy = false
        }
    }

    fun placeOrder(activity: Activity) {
        val cart = (state as? Load.Ready)?.value ?: return
        if (busy || !cart.allOrderable) return
        busy = true
        viewModelScope.launch {
            val key = checkoutKey?.takeIf { it.first == cart.totalPaise }
                ?: (cart.totalPaise to UUID.randomUUID().toString()).also { checkoutKey = it }
            val order = runCatching { repo.checkout(key.second, cart.totalPaise) }.getOrElse {
                message = friendlyError(it)
                if ((it as? ApiException)?.code in setOf("PRICE_CHANGED", "CART_ITEM_UNAVAILABLE")) load()
                busy = false
                return@launch
            }
            checkoutKey = null
            message = payForOrder(repo, activity, order.id)
            busy = false
            placedOrderId = order.id
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CartScreen(onBack: () -> Unit, onOrderPlaced: (String) -> Unit) {
    val vm = repoViewModel { CartViewModel(it) }
    val activity = LocalContext.current as Activity
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(vm.message) { vm.message?.let { snackbar.showSnackbar(it); vm.message = null } }
    LaunchedEffect(vm.placedOrderId) {
        vm.placedOrderId?.let { vm.placedOrderId = null; onOrderPlaced(it) }
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Your cart") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            LoadContent(vm.state, onRetry = vm::load) { cart ->
                if (cart.lines.isEmpty()) {
                    Message("Your cart is empty. Add items from a canteen menu.")
                    return@LoadContent
                }
                LazyColumn(
                    Modifier.weight(1f),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(cart.lines, key = { it.variantId }) { line -> CartLineCard(line, vm) }
                }
                CheckoutPanel(cart, vm.busy) { vm.placeOrder(activity) }
            }
        }
    }
}

@Composable
private fun CartLineCard(line: CartLine, vm: CartViewModel) {
    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(line.itemName, fontWeight = FontWeight.SemiBold)
                Text("${line.variant} · ${line.unitPricePaise?.let(::rupees) ?: "—"}", color = Muted)
                if (!line.orderable) {
                    Text("Currently unavailable – remove to continue", color = DangerRed, style = MaterialTheme.typography.bodySmall)
                }
            }
            QuantityStepper(line.quantity, !vm.busy, { vm.setQuantity(line, it) }, line.itemName)
        }
    }
}

@Composable
private fun CheckoutPanel(cart: Cart, busy: Boolean, onPay: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(16.dp)) {
        HorizontalDivider()
        Row(Modifier.fillMaxWidth().padding(vertical = 12.dp)) {
            Text("Total (${cart.itemCount} items)", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            Text(rupees(cart.totalPaise), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
        Text("Pay by UPI or card through Razorpay. One pickup code covers the whole order.", color = Muted, style = MaterialTheme.typography.bodySmall)
        Button(
            onClick = onPay,
            enabled = !busy && cart.allOrderable,
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp).height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = PayGreen, contentColor = Color.White),
        ) {
            if (busy) CircularProgressIndicator(Modifier.size(22.dp), color = Color.White, strokeWidth = 2.dp)
            else Text("Pay ${rupees(cart.totalPaise)}", fontWeight = FontWeight.SemiBold)
        }
    }
}
