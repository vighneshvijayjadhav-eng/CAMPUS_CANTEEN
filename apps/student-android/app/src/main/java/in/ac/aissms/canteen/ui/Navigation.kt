package `in`.ac.aissms.canteen.ui

import android.net.Uri
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import `in`.ac.aissms.canteen.CanteenApplication
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.ui.screens.CartScreen
import `in`.ac.aissms.canteen.ui.screens.HomeScreen
import `in`.ac.aissms.canteen.ui.screens.MenuScreen
import `in`.ac.aissms.canteen.ui.screens.OrderScreen
import `in`.ac.aissms.canteen.ui.screens.OrdersScreen
import `in`.ac.aissms.canteen.ui.screens.ProfileScreen
import `in`.ac.aissms.canteen.ui.screens.SignInScreen

@Composable
fun repository(): CanteenRepository =
    (LocalContext.current.applicationContext as CanteenApplication).repository

@Composable
inline fun <reified VM : ViewModel> repoViewModel(
    key: String? = null,
    crossinline create: (CanteenRepository) -> VM,
): VM {
    val repo = repository()
    return viewModel(key = key, factory = viewModelFactory { initializer { create(repo) } })
}

object Routes {
    const val HOME = "home"
    const val ORDERS = "orders"
    const val PROFILE = "profile"
    const val CART = "cart"
    fun menu(canteenId: String, name: String) = "menu/$canteenId/${Uri.encode(name)}"
    fun order(orderId: String) = "order/$orderId"
}

private val tabs = listOf(
    Triple(Routes.HOME, "Home", Icons.Filled.Home),
    Triple(Routes.ORDERS, "Orders", Icons.Filled.ReceiptLong),
    Triple(Routes.PROFILE, "Profile", Icons.Filled.Person),
)

@Composable
fun CanteenApp() {
    val repo = repository()
    val signedIn by repo.signedIn.collectAsStateWithLifecycle()
    if (!signedIn) {
        SignInScreen()
        return
    }
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route
    Scaffold(
        bottomBar = {
            if (tabs.any { it.first == route }) {
                NavigationBar {
                    tabs.forEach { (target, label, icon) ->
                        NavigationBarItem(
                            selected = route == target,
                            onClick = { nav.switchTab(target) },
                            icon = { Icon(icon, contentDescription = null) },
                            label = { Text(label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(nav, startDestination = Routes.HOME, modifier = Modifier.padding(padding)) {
            composable(Routes.HOME) {
                HomeScreen(onOpenCanteen = { id, name -> nav.navigate(Routes.menu(id, name)) })
            }
            composable("menu/{canteenId}/{name}") { back ->
                MenuScreen(
                    canteenId = back.arguments?.getString("canteenId").orEmpty(),
                    canteenName = back.arguments?.getString("name").orEmpty(),
                    onBack = { nav.popBackStack() },
                    onOpenCart = { nav.navigate(Routes.CART) },
                )
            }
            composable(Routes.CART) {
                CartScreen(
                    onBack = { nav.popBackStack() },
                    onOrderPlaced = { orderId ->
                        nav.navigate(Routes.order(orderId)) { popUpTo(Routes.HOME) }
                    },
                )
            }
            composable("order/{orderId}") { back ->
                OrderScreen(
                    orderId = back.arguments?.getString("orderId").orEmpty(),
                    onBack = { if (!nav.popBackStack()) nav.switchTab(Routes.ORDERS) },
                )
            }
            composable(Routes.ORDERS) {
                OrdersScreen(onOpenOrder = { nav.navigate(Routes.order(it)) })
            }
            composable(Routes.PROFILE) { ProfileScreen() }
        }
    }
}

private fun NavHostController.switchTab(route: String) = navigate(route) {
    popUpTo(graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}
