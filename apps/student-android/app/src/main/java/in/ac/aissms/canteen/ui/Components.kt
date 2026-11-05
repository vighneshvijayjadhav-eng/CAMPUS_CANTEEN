package `in`.ac.aissms.canteen.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import `in`.ac.aissms.canteen.ui.theme.DangerRed
import `in`.ac.aissms.canteen.ui.theme.Muted
import `in`.ac.aissms.canteen.ui.theme.OpenGreen

/** Screen load state shared by every screen. */
sealed interface Load<out T> {
    data object Loading : Load<Nothing>
    data class Ready<T>(val value: T) : Load<T>
    data class Failed(val message: String) : Load<Nothing>
}

@Composable
fun <T> LoadContent(state: Load<T>, onRetry: () -> Unit, content: @Composable (T) -> Unit) {
    when (state) {
        Load.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        is Load.Failed -> Message(state.message, actionLabel = "Try again", onAction = onRetry)
        is Load.Ready -> content(state.value)
    }
}

@Composable
fun Message(text: String, actionLabel: String? = null, onAction: (() -> Unit)? = null) {
    Column(
        Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(text, textAlign = TextAlign.Center, color = Muted)
        if (actionLabel != null && onAction != null) {
            OutlinedButton(onClick = onAction, modifier = Modifier.padding(top = 16.dp)) {
                Text(actionLabel)
            }
        }
    }
}

@Composable
fun Badge(text: String, color: Color) {
    Text(
        text.uppercase(),
        modifier = Modifier
            .background(color.copy(alpha = 0.12f), RoundedCornerShape(50))
            .padding(horizontal = 8.dp, vertical = 2.dp),
        color = color,
        style = MaterialTheme.typography.labelSmall,
        fontWeight = FontWeight.Bold,
    )
}

fun stateColor(state: String): Color = when (state) {
    "COLLECTED" -> OpenGreen
    "CANCELLED" -> DangerRed
    "PAYMENT_PENDING" -> Color(0xFFB7791F)
    else -> Color(0xFF1E5BD8)
}

@Composable
fun QuantityStepper(quantity: Int, enabled: Boolean, onChange: (Int) -> Unit, itemName: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        FilledTonalIconButton(
            onClick = { onChange(quantity - 1) },
            enabled = enabled,
            modifier = Modifier.size(36.dp).semantics { contentDescription = "Remove one $itemName" },
        ) { Icon(Icons.Filled.Remove, contentDescription = null) }
        Text(
            quantity.toString(),
            modifier = Modifier.padding(horizontal = 12.dp),
            fontWeight = FontWeight.SemiBold,
        )
        FilledTonalIconButton(
            onClick = { onChange(quantity + 1) },
            enabled = enabled && quantity < 99,
            modifier = Modifier.size(36.dp).semantics { contentDescription = "Add one $itemName" },
        ) { Icon(Icons.Filled.Add, contentDescription = null) }
    }
}
