package `in`.ac.aissms.canteen.auth

import android.content.Context
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import `in`.ac.aissms.canteen.BuildConfig

sealed interface GoogleResult {
    data class Token(val idToken: String) : GoogleResult
    data object Cancelled : GoogleResult
    data class Failed(val message: String) : GoogleResult
}

/** Any Google account may sign in; the backend verifies the ID token's audience and issuer. */
object GoogleSignIn {
    val configured: Boolean get() = BuildConfig.GOOGLE_SERVER_CLIENT_ID.isNotBlank()

    suspend fun requestIdToken(activityContext: Context): GoogleResult {
        if (!configured) return GoogleResult.Failed("Google sign-in is not configured for this build.")
        val option = GetSignInWithGoogleOption.Builder(BuildConfig.GOOGLE_SERVER_CLIENT_ID).build()
        val request = GetCredentialRequest.Builder().addCredentialOption(option).build()
        return try {
            val credential = CredentialManager.create(activityContext)
                .getCredential(activityContext, request).credential
            if (credential is CustomCredential &&
                credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
            ) {
                GoogleResult.Token(GoogleIdTokenCredential.createFrom(credential.data).idToken)
            } else {
                GoogleResult.Failed("Unexpected credential type.")
            }
        } catch (_: GetCredentialCancellationException) {
            GoogleResult.Cancelled
        } catch (_: NoCredentialException) {
            GoogleResult.Failed(
                "No Google account on this phone. Add one in Settings › Passwords & accounts, then try again.",
            )
        } catch (_: GetCredentialException) {
            GoogleResult.Failed("Google sign-in didn't work. Check your connection and try again.")
        }
    }
}
