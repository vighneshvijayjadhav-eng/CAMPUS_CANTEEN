package `in`.ac.aissms.canteen.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.CanteenSummary
import `in`.ac.aissms.canteen.data.Institute
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.Message
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.theme.Blue
import `in`.ac.aissms.canteen.ui.theme.DangerRed
import `in`.ac.aissms.canteen.ui.theme.Muted
import `in`.ac.aissms.canteen.ui.theme.Navy
import `in`.ac.aissms.canteen.ui.theme.OpenGreen
import kotlinx.coroutines.launch

data class HomeData(
    val greetingName: String,
    val institutes: List<Institute>,
    val selected: Institute?,
    val canteens: List<CanteenSummary>,
)

class HomeViewModel(private val repo: CanteenRepository) : ViewModel() {
    var state by mutableStateOf<Load<HomeData>>(Load.Loading)
        private set

    init { load() }

    fun load() {
        viewModelScope.launch {
            state = Load.Loading
            state = runCatching {
                val me = repo.me()
                val institutes = repo.institutes()
                // Remembered on the server so it follows the student across devices.
                val selected = institutes.firstOrNull { it.id == me.selectedInstituteId }
                    ?: institutes.singleOrNull()
                HomeData(
                    me.displayName.substringBefore(' '),
                    institutes,
                    selected,
                    selected?.let { repo.canteens(it.id) }.orEmpty(),
                )
            }.fold({ Load.Ready(it) }, { Load.Failed(friendlyError(it)) })
        }
    }

    fun choose(institute: Institute) {
        viewModelScope.launch {
            runCatching { repo.selectInstitute(institute.id) }
                .onSuccess { load() }
                .onFailure { state = Load.Failed(friendlyError(it)) }
        }
    }
}

@Composable
fun HomeScreen(onOpenCanteen: (String, String) -> Unit) {
    val vm = repoViewModel { HomeViewModel(it) }
    LoadContent(vm.state, onRetry = vm::load) { data ->
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
            Text(
                "Hello, ${data.greetingName}",
                modifier = Modifier.padding(top = 20.dp),
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                color = Navy,
            )
            Text("Order ahead, skip the queue.", color = Muted)
            Text(
                "Institute",
                modifier = Modifier.padding(top = 20.dp, bottom = 4.dp),
                style = MaterialTheme.typography.titleSmall,
            )
            Row(
                Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                data.institutes.forEach { institute ->
                    FilterChip(
                        selected = institute.id == data.selected?.id,
                        onClick = { vm.choose(institute) },
                        label = { Text(institute.name) },
                    )
                }
            }
            when {
                data.selected == null -> Message("Choose your institute to see its canteens.")
                data.canteens.isEmpty() -> Message("No canteens are listed for this institute yet.")
                else -> LazyColumn(
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        Text("Canteens", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    }
                    items(data.canteens, key = { it.id }) { canteen ->
                        CanteenCard(canteen) { onOpenCanteen(canteen.id, canteen.name) }
                    }
                }
            }
        }
    }
}

@Composable
private fun CanteenCard(canteen: CanteenSummary, onOpen: () -> Unit) {
    Card(Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
        Column(Modifier.padding(16.dp)) {
            Text(canteen.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                if (canteen.acceptingOrders) "● Open for orders" else "● Closed – browse only",
                color = if (canteen.acceptingOrders) OpenGreen else DangerRed,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 4.dp),
            )
            Text(
                "View menu →",
                color = Blue,
                style = MaterialTheme.typography.labelLarge,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
    }
}
