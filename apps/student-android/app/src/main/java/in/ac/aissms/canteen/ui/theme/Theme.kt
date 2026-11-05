package `in`.ac.aissms.canteen.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Palette from design-references/student-app-mockup.jpg: navy brand, blue actions, green pay.
val Navy = Color(0xFF0B2D62)
val Blue = Color(0xFF1E5BD8)
val PayGreen = Color(0xFF1F9D55)
val DangerRed = Color(0xFFD93A3A)
val Surface = Color(0xFFF7FAFF)
val Muted = Color(0xFF6B7A90)
val OpenGreen = Color(0xFF1F9D55)

private val Colors = lightColorScheme(
    primary = Blue,
    onPrimary = Color.White,
    secondary = Navy,
    onSecondary = Color.White,
    tertiary = PayGreen,
    error = DangerRed,
    background = Surface,
    surface = Color.White,
    surfaceVariant = Color(0xFFEEF3FB),
    onSurfaceVariant = Muted,
    outline = Color(0xFFD6DFEC),
)

@Composable
fun CanteenTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Colors, content = content)
}
