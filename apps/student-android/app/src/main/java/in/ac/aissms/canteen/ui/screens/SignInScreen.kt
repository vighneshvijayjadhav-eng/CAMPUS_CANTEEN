package `in`.ac.aissms.canteen.ui.screens

import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.ac.aissms.canteen.auth.GoogleResult
import `in`.ac.aissms.canteen.auth.GoogleSignIn
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.theme.Navy
import kotlinx.coroutines.launch

class SignInViewModel(private val repo: CanteenRepository) : ViewModel() {
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    fun signIn(request: suspend () -> GoogleResult) {
        if (busy) return
        busy = true
        error = null
        viewModelScope.launch {
            when (val result = request()) {
                is GoogleResult.Token -> runCatching {
                    repo.signInWithGoogle(result.idToken, "${Build.MANUFACTURER} ${Build.MODEL}")
                }.onFailure { error = friendlyError(it) }
                is GoogleResult.Failed -> error = result.message
                GoogleResult.Cancelled -> Unit
            }
            busy = false
        }
    }
}

@Composable
fun SignInScreen() {
    val vm = repoViewModel { SignInViewModel(it) }
    val context = LocalContext.current
    Column(
        Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(Navy, Color(0xFF13234A))))
            .padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            "AISSMS",
            style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.Bold,
            color = Color.White,
        )
        Text("Campus Canteen", style = MaterialTheme.typography.titleLarge, color = Color.White)
        Text(
            "Good Food. A Better Campus.",
            modifier = Modifier.padding(top = 12.dp),
            color = Color.White.copy(alpha = 0.8f),
        )
        Spacer(Modifier.height(48.dp))
        Button(
            onClick = { vm.signIn { GoogleSignIn.requestIdToken(context) } },
            enabled = !vm.busy && GoogleSignIn.configured,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Navy),
        ) {
            if (vm.busy) {
                CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            } else {
                Text("Continue with Google", fontWeight = FontWeight.SemiBold)
            }
        }
        val note = when {
            !GoogleSignIn.configured ->
                "This build has no Google OAuth client configured, so sign-in is disabled."
            vm.error != null -> vm.error
            else -> "Any Google account works. You'll choose your institute next."
        }
        Text(
            note.orEmpty(),
            modifier = Modifier.padding(top = 16.dp),
            color = if (vm.error != null) Color(0xFFFFC9C9) else Color.White.copy(alpha = 0.75f),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}
