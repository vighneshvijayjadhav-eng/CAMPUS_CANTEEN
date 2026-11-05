package `in`.ac.aissms.canteen.ui.screens

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import coil.compose.AsyncImage
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.Review
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.repository
import `in`.ac.aissms.canteen.ui.theme.Muted
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream

const val MAX_REVIEW_PHOTOS = 3

/** Shrinks a picked photo to at most 1600 px and re-encodes it as JPEG before upload. The server
 *  re-encodes again (and strips metadata); doing it here keeps uploads small on mobile data. */
suspend fun compressPhoto(context: Context, uri: Uri): ByteArray = withContext(Dispatchers.IO) {
    val bitmap = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
        val source = ImageDecoder.createSource(context.contentResolver, uri)
        ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
            val longest = maxOf(info.size.width, info.size.height)
            if (longest > 1600) {
                val scale = 1600f / longest
                decoder.setTargetSize((info.size.width * scale).toInt(), (info.size.height * scale).toInt())
            }
            decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
        }
    } else {
        decodeScaledLegacy(context, uri)
    }
    ByteArrayOutputStream().use { out ->
        bitmap.compress(Bitmap.CompressFormat.JPEG, 85, out)
        bitmap.recycle()
        out.toByteArray()
    }
}

private fun decodeScaledLegacy(context: Context, uri: Uri): Bitmap {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, bounds) }
    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= 1600) sample *= 2
    val decoded = context.contentResolver.openInputStream(uri).use {
        BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
    } ?: throw IllegalArgumentException("Unreadable image")
    val longest = maxOf(decoded.width, decoded.height)
    if (longest <= 1600) return decoded
    val scale = 1600f / longest
    return Bitmap.createScaledBitmap(decoded, (decoded.width * scale).toInt(), (decoded.height * scale).toInt(), true)
        .also { if (it !== decoded) decoded.recycle() }
}

class WriteReviewViewModel(
    private val repo: CanteenRepository,
    private val lineId: String,
    private val existingId: String?,
) : ViewModel() {
    var rating by mutableIntStateOf(0)
    var body by mutableStateOf("")
    var review by mutableStateOf<Review?>(null)
        private set
    var busy by mutableStateOf(existingId != null)
        private set
    var message by mutableStateOf<String?>(null)
    var done by mutableStateOf(false)

    init {
        if (existingId != null) {
            viewModelScope.launch {
                runCatching { repo.myReviews().firstOrNull { it.id == existingId } }
                    .onSuccess { found ->
                        review = found
                        found?.let { rating = it.rating; body = it.body.orEmpty() }
                    }
                    .onFailure { message = friendlyError(it) }
                busy = false
            }
        }
    }

    fun save(context: Context, newPhotos: List<Uri>) {
        if (busy || rating == 0) return
        busy = true
        viewModelScope.launch {
            runCatching {
                var saved = review?.let { repo.editReview(it.id, rating, body.trim().ifEmpty { null }) }
                    ?: repo.writeReview(lineId, rating, body.trim().ifEmpty { null })
                review = saved
                for (uri in newPhotos) {
                    saved = repo.uploadReviewPhoto(saved.id, compressPhoto(context, uri))
                    review = saved
                }
            }.onSuccess { done = true }.onFailure { message = friendlyError(it) }
            busy = false
        }
    }

    fun deletePhoto(photoId: String) {
        val current = review ?: return
        busy = true
        viewModelScope.launch {
            runCatching { repo.deleteReviewPhoto(current.id, photoId) }
                .onSuccess { review = it }
                .onFailure { message = friendlyError(it) }
            busy = false
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WriteReviewScreen(lineId: String, reviewId: String?, itemName: String, onDone: () -> Unit) {
    val vm = repoViewModel(key = "write-$lineId") { WriteReviewViewModel(it, lineId, reviewId) }
    val repo = repository()
    val context = LocalContext.current
    val snackbar = remember { SnackbarHostState() }
    var picked by remember { mutableStateOf<List<Uri>>(emptyList()) }
    val existing = vm.review?.photos.orEmpty()
    val room = MAX_REVIEW_PHOTOS - existing.size - picked.size
    // System photo picker: no storage permission needed; only the chosen photos are shared.
    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickMultipleVisualMedia(MAX_REVIEW_PHOTOS),
    ) { uris -> picked = (picked + uris).distinct().take(MAX_REVIEW_PHOTOS - existing.size) }
    LaunchedEffect(vm.message) { vm.message?.let { snackbar.showSnackbar(it); vm.message = null } }
    LaunchedEffect(vm.done) { if (vm.done) onDone() }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (reviewId == null) "Review $itemName" else "Edit review") },
                navigationIcon = {
                    IconButton(onClick = onDone) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text("How was it?", style = MaterialTheme.typography.titleMedium)
            Row {
                (1..5).forEach { value ->
                    TextButton(
                        onClick = { vm.rating = value },
                        modifier = Modifier.semantics { contentDescription = "$value star${if (value > 1) "s" else ""}" },
                    ) {
                        Text(if (value <= vm.rating) "★" else "☆", fontSize = 34.sp, color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
            OutlinedTextField(
                value = vm.body,
                onValueChange = { if (it.length <= 1000) vm.body = it },
                label = { Text("Comment (optional)") },
                supportingText = { Text("${vm.body.length}/1000") },
                modifier = Modifier.fillMaxWidth().height(160.dp),
            )
            Text("Photos (up to $MAX_REVIEW_PHOTOS)", style = MaterialTheme.typography.titleSmall)
            Text("Photos are public on the menu. Don't include people's faces or personal details.", color = Muted, style = MaterialTheme.typography.bodySmall)
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                existing.forEach { photo ->
                    PhotoTile(repo.mediaUrl(photo.url)) { vm.deletePhoto(photo.id) }
                }
                picked.forEach { uri -> PhotoTile(uri) { picked = picked - uri } }
            }
            if (room > 0) {
                OutlinedButton(
                    onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                    enabled = !vm.busy,
                ) { Text("Add photos") }
            }
            Button(
                onClick = { vm.save(context, picked) },
                enabled = !vm.busy && vm.rating > 0,
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) {
                if (vm.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                else Text(if (reviewId == null) "Post review" else "Save changes")
            }
            Text("Reviews are published straight away. Other students can report reviews that break the rules.", color = Muted, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun PhotoTile(model: Any, onRemove: () -> Unit) {
    Box {
        AsyncImage(
            model = model,
            contentDescription = "Selected photo",
            contentScale = ContentScale.Crop,
            modifier = Modifier.size(96.dp).clip(RoundedCornerShape(8.dp)),
        )
        FilledTonalIconButton(
            onClick = onRemove,
            modifier = Modifier.align(Alignment.TopEnd).size(28.dp).semantics { contentDescription = "Remove photo" },
        ) { Icon(Icons.Filled.Close, contentDescription = null, modifier = Modifier.size(16.dp)) }
    }
}
