from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    pickup_hmac_key: SecretStr
    web_origin: str = "http://localhost:5173"
    google_oauth_client_id: str | None = None
    environment: Literal["local", "staging", "production"] = "local"

    @model_validator(mode="after")
    def validate_security(self):
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("The application requires PostgreSQL with psycopg")
        if len(self.pickup_hmac_key.get_secret_value()) < 32:
            raise ValueError("PICKUP_HMAC_KEY must contain at least 32 random characters")
        if self.environment != "local" and not self.web_origin.startswith("https://"):
            raise ValueError("HTTPS is required outside local development")
        return self
