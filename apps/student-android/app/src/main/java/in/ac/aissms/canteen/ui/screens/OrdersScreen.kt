package `in`.ac.aissms.canteen.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.OrderSummary
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.data.isActive
import `in`.ac.aissms.canteen.data.orderTime
import `in`.ac.aissms.canteen.data.refundLabel
import `in`.ac.aissms.canteen.data.rupees
import `in`.ac.aissms.canteen.ui.Badge
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.Message
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.stateColor
import `in`.ac.aissms.canteen.ui.theme.Muted
import kotlinx.coroutines.launch

class OrdersViewModel(private val repo: CanteenRepository) : ViewModel() {
    var state by mutableStateOf<Load<List<OrderSummary>>>(Load.Loading)
        private set

    fun load() {
        viewModelScope.launch {
            if (state !is Load.Ready) state = Load.Loading
            state = runCatching { repo.orders() }.fold({ Load.Ready(it) }, { Load.Failed(friendlyError(it)) })
        }
    }
}

@Composable
fun OrdersScreen(onOpenOrder: (String) -> Unit) {
    val vm = repoViewModel { OrdersViewModel(it) }
    LaunchedEffect(Unit) { vm.load() } // refresh each time the tab is shown
    var tab by rememberSaveable { mutableIntStateOf(0) }
    Column(Modifier.fillMaxSize()) {
        TabRow(selectedTabIndex = tab) {
            Tab(tab == 0, { tab = 0 }, text = { Text("Active") })
            Tab(tab == 1, { tab = 1 }, text = { Text("History") })
        }
        LoadContent(vm.state, onRetry = vm::load) { orders ->
            val shown = orders.filter { isActive(it.state) == (tab == 0) }
            if (shown.isEmpty()) {
                Message(if (tab == 0) "No active orders." else "No past orders yet.")
            } else {
                LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(shown, key = { it.id }) { order -> OrderRow(order) { onOpenOrder(order.id) } }
                }
            }
        }
    }
}

@Composable
private fun OrderRow(order: OrderSummary, onOpen: () -> Unit) {
    Card(Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(order.canteenName.orEmpty(), fontWeight = FontWeight.SemiBold)
                Text(orderTime(order.createdAt), color = Muted, style = MaterialTheme.typography.bodySmall)
                Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Badge(order.stateLabel, stateColor(order.state))
                    refundLabel(order.refundStatus)?.let { Text(it, color = Muted, style = MaterialTheme.typography.bodySmall) }
                }
            }
            Text(rupees(order.totalPaise), fontWeight = FontWeight.SemiBold)
        }
    }
}
