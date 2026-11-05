package `in`.ac.aissms.canteen.ui.screens

import android.app.Activity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.OrderDetail
import `in`.ac.aissms.canteen.data.cancelSecondsLeft
import `in`.ac.aissms.canteen.data.countdown
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.data.orderTime
import `in`.ac.aissms.canteen.data.refundLabel
import `in`.ac.aissms.canteen.data.rupees
import `in`.ac.aissms.canteen.payments.payForOrder
import `in`.ac.aissms.canteen.ui.Badge
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.stateColor
import `in`.ac.aissms.canteen.ui.theme.Blue
import `in`.ac.aissms.canteen.ui.theme.DangerRed
import `in`.ac.aissms.canteen.ui.theme.Muted
import `in`.ac.aissms.canteen.ui.theme.Navy
import `in`.ac.aissms.canteen.ui.theme.PayGreen
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.Instant

class OrderViewModel(private val repo: CanteenRepository, private val orderId: String) : ViewModel() {
    var state by mutableStateOf<Load<OrderDetail>>(Load.Loading)
        private set
    var busy by mutableStateOf(false)
        private set
    var message by mutableStateOf<String?>(null)
    var now by mutableStateOf(Instant.now())
        private set

    init {
        load()
        viewModelScope.launch {
            var tick = 0L
            while (isActive) {
                delay(1_000)
                now = Instant.now()
                tick++
                val order = (state as? Load.Ready)?.value ?: continue
                // Refresh hints only; the server stays authoritative for every state change.
                val every = when (order.state) {
                    "PAYMENT_PENDING" -> 4
                    "PAID_ACTIVE", "PARTIALLY_COLLECTED" -> 15
                    "CANCELLED" -> if (order.refundStatus in setOf("REQUESTED", "PENDING")) 30 else 0
                    else -> 0
                }
                if (every > 0 && tick % every == 0L && !busy) refresh()
            }
        }
    }

    fun load() {
        viewModelScope.launch {
            if (state !is Load.Ready) state = Load.Loading
            refresh()
        }
    }

    private suspend fun refresh() {
        runCatching { repo.order(orderId) }
            .onSuccess { state = Load.Ready(it) }
            .onFailure { if (state !is Load.Ready) state = Load.Failed(friendlyError(it)) }
    }

    fun cancel() {
        busy = true
        viewModelScope.launch {
            runCatching { repo.cancelOrder(orderId) }
                .onSuccess {
                    state = Load.Ready(it)
                    message = if (it.state == "CANCELLED") "Order cancelled." else
                        "Some items were already handed over, so the canteen will review your request."
                }
                .onFailure { message = friendlyError(it) }
            busy = false
        }
    }

    fun payAgain(activity: Activity) {
        busy = true
        viewModelScope.launch {
            message = payForOrder(repo, activity, orderId)
            refresh()
            busy = false
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OrderScreen(orderId: String, onBack: () -> Unit) {
    val vm = repoViewModel(key = "order-$orderId") { OrderViewModel(it, orderId) }
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(vm.message) { vm.message?.let { snackbar.showSnackbar(it); vm.message = null } }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Order") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            LoadContent(vm.state, onRetry = vm::load) { order -> OrderBody(order, vm) }
        }
    }
}

@Composable
private fun OrderBody(order: OrderDetail, vm: OrderViewModel) {
    val activity = LocalContext.current as Activity
    var confirmCancel by remember { mutableStateOf(false) }
    val secondsLeft = cancelSecondsLeft(order, vm.now)
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(order.canteenName.orEmpty(), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("Order #${order.id.take(8).uppercase()} · ${orderTime(order.createdAt)}", color = Muted, style = MaterialTheme.typography.bodySmall)
            }
            Badge(order.stateLabel, stateColor(order.state))
        }

        order.pickupCode?.let { PickupCode(it) }

        if (order.state == "PAYMENT_PENDING") {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text("Awaiting payment", fontWeight = FontWeight.SemiBold)
                    Text(
                        order.payment?.failureReason?.let { "Last attempt failed: $it" }
                            ?: "If you've paid, this updates within a few seconds. Otherwise pay now.",
                        color = Muted,
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Button(
                        onClick = { vm.payAgain(activity) },
                        enabled = !vm.busy,
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = PayGreen),
                    ) { Text("Pay ${rupees(order.totalPaise)}") }
                    TextButton(onClick = { confirmCancel = true }, enabled = !vm.busy) { Text("Cancel order") }
                }
            }
        }

        if (order.state == "PARTIALLY_COLLECTED" && order.remainingByStation.isNotEmpty()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text("Still to collect", fontWeight = FontWeight.SemiBold)
                    order.remainingByStation.forEach {
                        Text("${it.station}: ${it.remaining} item(s)", color = Muted)
                    }
                    Text("Show the same code at each counter.", style = MaterialTheme.typography.bodySmall, color = Muted)
                }
            }
        }

        if (order.exceptionStatus != null) {
            Text("Your cancellation request is with the canteen staff for review.", color = Blue)
        }
        refundLabel(order.refundStatus)?.let {
            Text(it, color = if (order.refundStatus == "FAILED") DangerRed else Blue, fontWeight = FontWeight.SemiBold)
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Order summary", fontWeight = FontWeight.SemiBold)
                order.lines.forEach { line ->
                    Row(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                        Column(Modifier.weight(1f)) {
                            Text("${line.quantity} × ${line.name} (${line.variant})")
                            val status = when {
                                line.remaining == 0 -> "Collected"
                                line.fulfilled > 0 -> "${line.fulfilled} of ${line.quantity} collected"
                                else -> "Collect at ${line.station}"
                            }
                            Text(status, color = Muted, style = MaterialTheme.typography.bodySmall)
                        }
                        Text(rupees(line.lineTotalPaise))
                    }
                }
                HorizontalDivider(Modifier.padding(vertical = 10.dp))
                Row {
                    Text("Total", Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                    Text(rupees(order.totalPaise), fontWeight = FontWeight.Bold)
                }
                order.payment?.takeIf { it.status == "CAPTURED" }?.let {
                    Text("Paid via Razorpay · ${it.providerPaymentId}", color = Muted, style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        if (secondsLeft != null) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("Cancel available for", color = Muted)
                    Text(countdown(secondsLeft), style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, color = PayGreen)
                    OutlinedButton(
                        onClick = { confirmCancel = true },
                        enabled = !vm.busy,
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = DangerRed),
                    ) { Text("Cancel order") }
                }
            }
        }
    }
    if (confirmCancel) {
        val paid = order.state != "PAYMENT_PENDING"
        AlertDialog(
            onDismissRequest = { confirmCancel = false },
            title = { Text("Cancel this order?") },
            text = {
                Text(
                    if (paid) "Your pickup code stops working and ${rupees(order.totalPaise)} is refunded to your payment method."
                    else "This unpaid order will be removed.",
                )
            },
            confirmButton = {
                TextButton(onClick = { confirmCancel = false; vm.cancel() }) { Text("Cancel order", color = DangerRed) }
            },
            dismissButton = { TextButton(onClick = { confirmCancel = false }) { Text("Keep order") } },
        )
    }
}

@Composable
private fun PickupCode(code: String) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Pickup code", color = Muted)
            Row(
                Modifier.padding(top = 8.dp).semantics { contentDescription = "Pickup code ${code.toList().joinToString(" ")}" },
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                code.forEach { digit ->
                    Box(
                        Modifier.size(width = 42.dp, height = 54.dp)
                            .background(Color(0xFFEEF3FB), RoundedCornerShape(10.dp)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(digit.toString(), fontSize = 30.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, color = Navy)
                    }
                }
            }
            Text(
                "Show this code at the counter. It stays valid until everything is collected.",
                modifier = Modifier.padding(top = 10.dp).height(40.dp),
                color = Muted,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
