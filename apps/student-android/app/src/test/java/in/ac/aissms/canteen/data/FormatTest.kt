package `in`.ac.aissms.canteen.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class FormatTest {
    @Test
    fun rupeesFromPaise() {
        assertEquals("₹40", rupees(4000))
        assertEquals("₹40.50", rupees(4050))
        assertEquals("₹0.05", rupees(5))
    }

    private fun order(state: String = "PAID_ACTIVE", paidAt: String? = "2026-11-05T06:30:00+00:00", fulfilled: Int = 0) =
        OrderDetail(
            id = "o",
            canteenId = "c",
            state = state,
            stateLabel = state,
            totalPaise = 8000,
            createdAt = "2026-11-05T06:29:00Z",
            paymentVerifiedAt = paidAt,
            lines = listOf(OrderLine("l", "Coffee", "Regular", "Juice", 4000, 2, 8000, fulfilled, 2 - fulfilled)),
        )

    @Test
    fun cancelCountdownFollowsFiveMinuteWindow() {
        val paid = Instant.parse("2026-11-05T06:30:00Z")
        assertEquals(300L, cancelSecondsLeft(order(), paid))
        assertEquals(1L, cancelSecondsLeft(order(), paid.plusSeconds(299)))
        assertNull(cancelSecondsLeft(order(), paid.plusSeconds(300)))
        assertNull(cancelSecondsLeft(order(fulfilled = 1), paid))
        assertNull(cancelSecondsLeft(order(state = "PAYMENT_PENDING", paidAt = null), paid))
        assertEquals("4:05", countdown(245))
    }

    @Test
    fun parsesServerTimestamps() {
        assertEquals(Instant.parse("2026-11-05T06:30:00Z"), parseInstant("2026-11-05T06:30:00Z"))
        assertEquals(Instant.parse("2026-11-05T06:30:00Z"), parseInstant("2026-11-05T12:00:00+05:30"))
        assertNull(parseInstant("not a time"))
        assertEquals("5 Nov, 12:00 PM", orderTime("2026-11-05T06:30:00Z"))
    }

    @Test
    fun activeStatesAndOrderability() {
        assertTrue(isActive("PARTIALLY_COLLECTED"))
        assertFalse(isActive("COLLECTED"))
        assertTrue(MenuVariant("v", "Regular", 4000, verified = true, available = true).orderable)
        assertFalse(MenuVariant("v", "Regular", null, verified = true, available = true).orderable)
        assertFalse(MenuVariant("v", "Regular", 4000, verified = false, available = true).orderable)
    }

    @Test
    fun errorsAreFriendly() {
        assertEquals(
            "Prices changed since you opened your cart. Please check the new total.",
            friendlyError(ApiException(409, "PRICE_CHANGED")),
        )
        assertEquals("Something went wrong. Please try again.", friendlyError(IllegalStateException()))
    }
}
