package `in`.ac.aissms.canteen.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.ac.aissms.canteen.data.ApiException
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.Cart
import `in`.ac.aissms.canteen.data.MenuItem
import `in`.ac.aissms.canteen.data.MenuVariant
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.data.rupees
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.QuantityStepper
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.theme.DangerRed
import `in`.ac.aissms.canteen.ui.theme.Muted
import kotlinx.coroutines.async
import kotlinx.coroutines.launch

class MenuViewModel(private val repo: CanteenRepository, private val canteenId: String) : ViewModel() {
    var menu by mutableStateOf<Load<List<MenuItem>>>(Load.Loading)
        private set
    var cart by mutableStateOf(Cart())
        private set
    var busy by mutableStateOf(false)
        private set
    var message by mutableStateOf<String?>(null)
    /** Set when adding would mix canteens; the UI asks before clearing the other cart. */
    var pendingConflict by mutableStateOf<Pair<String, Int>?>(null)
        private set

    init { load() }

    fun load() {
        viewModelScope.launch {
            menu = Load.Loading
            runCatching {
                val items = async { repo.menu(canteenId) }
                val current = async { repo.cart() }
                cart = current.await()
                items.await()
            }.fold({ menu = Load.Ready(it) }, { menu = Load.Failed(friendlyError(it)) })
        }
    }

    fun quantity(variantId: String): Int =
        if (cart.canteenId == canteenId) cart.lines.firstOrNull { it.variantId == variantId }?.quantity ?: 0 else 0

    fun setQuantity(variantId: String, quantity: Int) {
        if (busy) return
        busy = true
        viewModelScope.launch {
            runCatching { repo.setCartQuantity(variantId, quantity) }
                .onSuccess { cart = it }
                .onFailure {
                    if ((it as? ApiException)?.code == "CART_CANTEEN_CONFLICT") {
                        pendingConflict = variantId to quantity
                    } else {
                        message = friendlyError(it)
                    }
                }
            busy = false
        }
    }

    fun resolveConflict(replace: Boolean) {
        val (variantId, quantity) = pendingConflict ?: return
        pendingConflict = null
        if (!replace) return
        viewModelScope.launch {
            runCatching { repo.clearCart() }.onSuccess { setQuantity(variantId, quantity) }
                .onFailure { message = friendlyError(it) }
        }
    }

    val cartHere: Boolean get() = cart.canteenId == canteenId && cart.itemCount > 0
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MenuScreen(
    canteenId: String,
    canteenName: String,
    onBack: () -> Unit,
    onOpenCart: () -> Unit,
    onOpenReviews: (String, String) -> Unit,
) {
    val vm = repoViewModel(key = "menu-$canteenId") { MenuViewModel(it, canteenId) }
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(vm.message) {
        vm.message?.let { snackbar.showSnackbar(it); vm.message = null }
    }
    var category by remember { mutableStateOf<String?>(null) }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(canteenName) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            if (vm.cartHere) {
                Button(
                    onClick = onOpenCart,
                    modifier = Modifier.fillMaxWidth().padding(16.dp).height(52.dp),
                ) {
                    Text("View cart · ${vm.cart.itemCount} items · ${rupees(vm.cart.totalPaise)}")
                }
            }
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            LoadContent(vm.menu, onRetry = vm::load) { items ->
                val categories = items.map { it.category }.distinct()
                Row(
                    Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    FilterChip(category == null, { category = null }, label = { Text("All") })
                    categories.forEach { name ->
                        FilterChip(category == name, { category = name }, label = { Text(name) })
                    }
                }
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(items.filter { category == null || it.category == category }, key = { it.id }) { item ->
                        MenuItemCard(item, vm) { onOpenReviews(item.id, item.name) }
                    }
                }
            }
        }
    }
    vm.pendingConflict?.let {
        AlertDialog(
            onDismissRequest = { vm.resolveConflict(false) },
            title = { Text("Start a new cart?") },
            text = { Text("Your cart has items from another canteen. One order can only come from one canteen.") },
            confirmButton = { TextButton(onClick = { vm.resolveConflict(true) }) { Text("Clear and add") } },
            dismissButton = { TextButton(onClick = { vm.resolveConflict(false) }) { Text("Keep my cart") } },
        )
    }
}

@Composable
private fun MenuItemCard(item: MenuItem, vm: MenuViewModel, onOpenReviews: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text(item.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            TextButton(onClick = onOpenReviews, contentPadding = PaddingValues(0.dp)) {
                Text(
                    item.ratingAverage?.let { "★ %.1f (%d) · Reviews".format(it, item.ratingCount) } ?: "No reviews yet",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            item.variants.forEach { variant -> VariantRow(item, variant, vm) }
        }
    }
}

@Composable
private fun VariantRow(item: MenuItem, variant: MenuVariant, vm: MenuViewModel) {
    val quantity = vm.quantity(variant.id)
    val label = if (item.variants.size > 1 || variant.label != "Regular") "${variant.label} · " else ""
    Row(
        Modifier.fillMaxWidth().padding(top = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(label + (variant.pricePaise?.let(::rupees) ?: "Price not set"))
            if (!variant.orderable) {
                Text("Currently unavailable", color = DangerRed, style = MaterialTheme.typography.bodySmall)
            }
        }
        when {
            !variant.orderable -> Text("—", color = Muted)
            quantity == 0 -> OutlinedButton(onClick = { vm.setQuantity(variant.id, 1) }, enabled = !vm.busy) {
                Text("+ Add")
            }
            else -> QuantityStepper(quantity, !vm.busy, { vm.setQuantity(variant.id, it) }, item.name)
        }
    }
}
