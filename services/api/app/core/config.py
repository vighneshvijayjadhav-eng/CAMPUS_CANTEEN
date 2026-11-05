from typing import Literal

from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RazorpayCredential(BaseModel):
    key_secret: SecretStr
    webhook_secret: SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    pickup_hmac_key: SecretStr
    web_origin: str = "http://localhost:5173"
    google_oauth_client_id: str | None = None
    environment: Literal["local", "staging", "production"] = "local"
    # JSON keyed by Razorpay key_id: {"rzp_test_x": {"key_secret": "...", "webhook_secret": "..."}}
    razorpay_credentials: dict[str, RazorpayCredential] = {}
    # Single-account shorthand, merged into razorpay_credentials when all three are set.
    razorpay_key_id: str | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None
    # Separate explicit approval is required before any live charge.
    allow_live_payments: bool = False

    @model_validator(mode="after")
    def validate_security(self):
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("The application requires PostgreSQL with psycopg")
        if len(self.pickup_hmac_key.get_secret_value()) < 32:
            raise ValueError("PICKUP_HMAC_KEY must contain at least 32 random characters")
        if self.environment != "local" and not self.web_origin.startswith("https://"):
            raise ValueError("HTTPS is required outside local development")
        if self.allow_live_payments and self.environment != "production":
            raise ValueError("Live payments may only be enabled in production")
        single = (self.razorpay_key_id, self.razorpay_key_secret, self.razorpay_webhook_secret)
        if all(single) and self.razorpay_key_secret.get_secret_value():
            self.razorpay_credentials = {
                **self.razorpay_credentials,
                self.razorpay_key_id: RazorpayCredential(
                    key_secret=self.razorpay_key_secret,
                    webhook_secret=self.razorpay_webhook_secret,
                ),
            }
        return self
