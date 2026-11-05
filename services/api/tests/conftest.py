"""Shared fixtures."""

from test_api import setup  # noqa: F401  (API client with seeded canteen)
from test_payments import pay_setup  # noqa: F401  (Razorpay fake + paid-order fixture)
