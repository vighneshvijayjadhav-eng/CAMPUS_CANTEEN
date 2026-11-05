package `in`.ac.aissms.canteen.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.Inbox
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.data.orderTime
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.Message
import `in`.ac.aissms.canteen.ui.theme.Muted
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/** Shared by the bottom-bar badge and the Alerts tab. In-app only: there is no OS push. */
class InboxViewModel(private val repo: CanteenRepository) : ViewModel() {
    var state by mutableStateOf<Load<Inbox>>(Load.Loading)
        private set
    var unread by mutableIntStateOf(0)
        private set

    init {
        viewModelScope.launch {
            while (isActive) {
                refresh()
                delay(30_000)
            }
        }
    }

    suspend fun refresh() {
        runCatching { repo.notifications() }
            .onSuccess { state = Load.Ready(it); unread = it.unread }
            .onFailure { if (state !is Load.Ready) state = Load.Failed(friendlyError(it)) }
    }

    fun reload() { viewModelScope.launch { refresh() } }

    /** Shows the list as it was (unread highlighted), then marks everything read on the server. */
    fun markRead() {
        if (unread == 0) return
        viewModelScope.launch {
            runCatching { repo.markNotificationsRead() }.onSuccess { unread = 0 }
        }
    }
}

@Composable
fun InboxScreen(vm: InboxViewModel, onOpenOrder: (String) -> Unit) {
    LaunchedEffect(Unit) { vm.refresh(); vm.markRead() }
    LoadContent(vm.state, onRetry = vm::reload) { inbox ->
        if (inbox.items.isEmpty()) {
            Message("No updates yet. Payment, collection and refund updates appear here.")
            return@LoadContent
        }
        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(inbox.items, key = { it.id }) { item ->
                Card(
                    Modifier.fillMaxWidth().clickable(enabled = item.orderId != null) { item.orderId?.let(onOpenOrder) },
                    colors = CardDefaults.cardColors(
                        containerColor = if (item.read) MaterialTheme.colorScheme.surface else Color(0xFFEAF1FD),
                    ),
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Text(item.title, fontWeight = if (item.read) FontWeight.Normal else FontWeight.Bold)
                        Text(item.body, modifier = Modifier.padding(top = 2.dp))
                        Text(orderTime(item.createdAt), color = Muted, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}
