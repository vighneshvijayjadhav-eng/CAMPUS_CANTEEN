package `in`.ac.aissms.canteen.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import `in`.ac.aissms.canteen.data.Me
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.theme.DangerRed
import `in`.ac.aissms.canteen.ui.theme.Muted
import `in`.ac.aissms.canteen.ui.theme.Navy
import kotlinx.coroutines.launch

class ProfileViewModel(private val repo: CanteenRepository) : ViewModel() {
    var state by mutableStateOf<Load<Me>>(Load.Loading)
        private set
    var signingOut by mutableStateOf(false)
        private set

    init { load() }

    fun load() {
        viewModelScope.launch {
            state = runCatching { repo.me() }.fold({ Load.Ready(it) }, { Load.Failed(friendlyError(it)) })
        }
    }

    fun signOut() {
        signingOut = true
        viewModelScope.launch { repo.signOut() }
    }
}

@Composable
fun ProfileScreen() {
    val vm = repoViewModel { ProfileViewModel(it) }
    LoadContent(vm.state, onRetry = vm::load) { me ->
        Column(Modifier.fillMaxSize().padding(20.dp)) {
            Text(me.displayName, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = Navy)
            Text(me.email, color = Muted)
            Text(
                "Change your institute from the Home tab. Signing out ends this device's session; " +
                    "your orders stay in your account.",
                modifier = Modifier.padding(top = 24.dp),
                color = Muted,
                style = MaterialTheme.typography.bodySmall,
            )
            OutlinedButton(
                onClick = vm::signOut,
                enabled = !vm.signingOut,
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            ) { Text("Sign out", color = DangerRed) }
        }
    }
}
