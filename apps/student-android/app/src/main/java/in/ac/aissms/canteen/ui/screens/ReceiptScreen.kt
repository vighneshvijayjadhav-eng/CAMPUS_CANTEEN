package `in`.ac.aissms.canteen.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.OrderDetail
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.data.orderTime
import `in`.ac.aissms.canteen.data.rupees
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.theme.Muted
import kotlinx.coroutines.launch

class ReceiptViewModel(private val repo: CanteenRepository, private val orderId: String) : ViewModel() {
    var state by mutableStateOf<Load<OrderDetail>>(Load.Loading)
        private set

    init { load() }

    fun load() {
        viewModelScope.launch {
            state = runCatching { repo.order(orderId) }.fold({ Load.Ready(it) }, { Load.Failed(friendlyError(it)) })
        }
    }
}

private val REFUND_TEXT = mapOf(
    "PROCESSED" to "Refunded",
    "PENDING" to "Refund in progress",
    "REQUESTED" to "Refund requested",
    "FAILED" to "Refund failed",
)

/** In-app receipt built from the server's immutable order snapshot (no PDF/share by decision). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReceiptScreen(orderId: String, onBack: () -> Unit) {
    val vm = repoViewModel(key = "receipt-$orderId") { ReceiptViewModel(it, orderId) }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Receipt") },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            LoadContent(vm.state, onRetry = vm::load) { order ->
                Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp)) {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(order.canteenName.orEmpty(), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                            Text("Order #${order.id.take(8).uppercase()}", fontFamily = FontFamily.Monospace)
                            Text("Placed ${orderTime(order.createdAt)}", color = Muted)
                            order.paymentVerifiedAt?.let { Text("Paid ${orderTime(it)}", color = Muted) }
                            HorizontalDivider(Modifier.padding(vertical = 8.dp))
                            order.lines.forEach { line ->
                                Row(Modifier.fillMaxWidth()) {
                                    Column(Modifier.weight(1f)) {
                                        Text("${line.name} (${line.variant})")
                                        Text("${line.quantity} × ${rupees(line.unitPricePaise)}", color = Muted, style = MaterialTheme.typography.bodySmall)
                                    }
                                    Text(rupees(line.lineTotalPaise))
                                }
                            }
                            HorizontalDivider(Modifier.padding(vertical = 8.dp))
                            Row(Modifier.fillMaxWidth()) {
                                Text("Total paid", Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                                Text(rupees(order.totalPaise), fontWeight = FontWeight.Bold)
                            }
                            order.payment?.takeIf { it.status == "CAPTURED" }?.let {
                                Text("Razorpay payment ${it.providerPaymentId}", color = Muted, style = MaterialTheme.typography.bodySmall)
                            }
                            order.refunds.forEach { refund ->
                                Row(Modifier.fillMaxWidth()) {
                                    Text(REFUND_TEXT[refund.status] ?: refund.status, Modifier.weight(1f), color = Muted)
                                    Text("−${rupees(refund.amountPaise)}", color = Muted)
                                }
                            }
                            Text("Status: ${order.stateLabel}", modifier = Modifier.padding(top = 8.dp))
                        }
                    }
                }
            }
        }
    }
}
