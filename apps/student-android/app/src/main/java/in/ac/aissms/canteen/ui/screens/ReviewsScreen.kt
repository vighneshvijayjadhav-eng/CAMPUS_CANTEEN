package `in`.ac.aissms.canteen.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import coil.compose.AsyncImage
import `in`.ac.aissms.canteen.data.CanteenRepository
import `in`.ac.aissms.canteen.data.Review
import `in`.ac.aissms.canteen.data.friendlyError
import `in`.ac.aissms.canteen.data.orderTime
import `in`.ac.aissms.canteen.ui.Load
import `in`.ac.aissms.canteen.ui.LoadContent
import `in`.ac.aissms.canteen.ui.Message
import `in`.ac.aissms.canteen.ui.repoViewModel
import `in`.ac.aissms.canteen.ui.repository
import `in`.ac.aissms.canteen.ui.theme.Muted
import kotlinx.coroutines.launch

private val REPORT_REASONS = listOf(
    "OFFENSIVE" to "Offensive or abusive",
    "SPAM" to "Spam or advertising",
    "IRRELEVANT" to "Not about this item",
    "PRIVACY" to "Shows private information",
    "OTHER" to "Something else",
)

class ReviewsViewModel(private val repo: CanteenRepository, private val itemId: String) : ViewModel() {
    var state by mutableStateOf<Load<List<Review>>>(Load.Loading)
        private set
    var message by mutableStateOf<String?>(null)

    init { load() }

    fun load() {
        viewModelScope.launch {
            state = runCatching { repo.itemReviews(itemId) }.fold({ Load.Ready(it) }, { Load.Failed(friendlyError(it)) })
        }
    }

    fun report(reviewId: String, reason: String) {
        viewModelScope.launch {
            message = runCatching { repo.reportReview(reviewId, reason) }
                .fold({ "Thanks. The canteen will review this report." }, { friendlyError(it) })
        }
    }
}

fun stars(rating: Int) = "★".repeat(rating) + "☆".repeat(5 - rating)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReviewsScreen(itemId: String, itemName: String, onBack: () -> Unit) {
    val vm = repoViewModel(key = "reviews-$itemId") { ReviewsViewModel(it, itemId) }
    val repo = repository()
    val snackbar = remember { SnackbarHostState() }
    var reporting by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(vm.message) { vm.message?.let { snackbar.showSnackbar(it); vm.message = null } }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(itemName) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            LoadContent(vm.state, onRetry = vm::load) { reviews ->
                if (reviews.isEmpty()) {
                    Message("No reviews yet. Students who collect this item can review it from their order.")
                    return@LoadContent
                }
                LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    item {
                        val average = reviews.map { it.rating }.average()
                        Text("%.1f ★ · %d reviews".format(average, reviews.size), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    }
                    items(reviews, key = { it.id }) { review ->
                        ReviewCard(review, repo::mediaUrl) { reporting = review.id }
                    }
                }
            }
        }
    }
    reporting?.let { reviewId ->
        var reason by remember { mutableStateOf(REPORT_REASONS.first().first) }
        AlertDialog(
            onDismissRequest = { reporting = null },
            title = { Text("Report review") },
            text = {
                Column {
                    REPORT_REASONS.forEach { (code, label) ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected = reason == code, onClick = { reason = code })
                            Text(label)
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { vm.report(reviewId, reason); reporting = null }) { Text("Report") } },
            dismissButton = { TextButton(onClick = { reporting = null }) { Text("Cancel") } },
        )
    }
}

@Composable
fun ReviewCard(review: Review, mediaUrl: (String) -> String, onReport: (() -> Unit)? = null) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    stars(review.rating),
                    modifier = Modifier.semantics { contentDescription = "${review.rating} out of 5 stars" },
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    "  ${review.author ?: "You"} · ${orderTime(review.createdAt)}${if (review.edited) " · edited" else ""}",
                    color = Muted,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.weight(1f),
                )
                if (onReport != null) TextButton(onClick = onReport) { Text("Report") }
            }
            review.body?.let { Text(it, modifier = Modifier.padding(top = 4.dp)) }
            if (review.photos.isNotEmpty()) {
                Row(
                    Modifier.padding(top = 8.dp).horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    review.photos.forEach { photo ->
                        AsyncImage(
                            model = mediaUrl(photo.url),
                            contentDescription = "Photo from a student",
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.size(96.dp).clip(RoundedCornerShape(8.dp)),
                        )
                    }
                }
            }
        }
    }
}
