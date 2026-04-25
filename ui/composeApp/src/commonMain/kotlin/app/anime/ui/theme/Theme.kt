package app.anime.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// ----------------------------- Palette ----------------------------------------
val DarkBackground   = Color(0xFF0F0F0F)
val DarkSurface      = Color(0xFF1C1C1E)
val DarkSurfaceVar   = Color(0xFF2C2C2E)
val AccentBlue       = Color(0xFF4A9EFF)
val AccentBlueDim    = Color(0xFF1C5FAF)
val OnDark           = Color(0xFFECECEC)
val OnDarkSecondary  = Color(0xFF8E8E93)
val ErrorRed         = Color(0xFFFF453A)

private val DarkColorScheme = darkColorScheme(
    primary           = AccentBlue,
    onPrimary         = Color.Black,
    primaryContainer  = AccentBlueDim,
    secondary         = Color(0xFF636366),
    background        = DarkBackground,
    surface           = DarkSurface,
    surfaceVariant    = DarkSurfaceVar,
    onBackground      = OnDark,
    onSurface         = OnDark,
    onSurfaceVariant  = OnDarkSecondary,
    error             = ErrorRed,
)

@Composable
fun AnimePlayerTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    // App is always dark — anime content looks best on dark bg
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = AnimeTypography,
        content = content,
    )
}
