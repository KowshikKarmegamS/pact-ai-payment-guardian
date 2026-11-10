"""Application configuration loaded from environment variables or .env file."""

from functools import lru_cache
from typing import List, Union
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

# PayPal hosts PACT is allowed to talk to. Production (api-m.paypal.com) is
# deliberately absent: PACT is a Sandbox-only demonstration.
PAYPAL_SANDBOX_HOSTS = {"api-m.sandbox.paypal.com", "api.sandbox.paypal.com"}

SUPPORTED_CURRENCIES = {
    "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "SGD", "HKD", "NZD", "CHF",
    "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "ILS", "MXN", "PHP", "THB", "TWD",
}


class Settings(BaseSettings):
    """Application settings with secure credential handling.

    Sensitive fields are masked in representations to prevent accidental logging.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./pact.db"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = 20.0
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    PAYPAL_CURRENCY: str = "USD"
    PAYPAL_TIMEOUT_SECONDS: float = 20.0
    # Public URL of the web app. PayPal redirects the buyer here after checkout.
    APP_BASE_URL: str = "http://localhost:5173"
    APP_SECRET_KEY: str = "change-this-to-a-random-secret"
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://localhost:3000"
    # Directory containing the built React app. When it exists, FastAPI serves it.
    FRONTEND_DIST: str = "../frontend/dist"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a list of strings."""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return ["http://localhost:5173", "http://localhost:3000"]

    @property
    def currency(self) -> str:
        """The single currency used for catalog, mandates and PayPal orders."""
        return (self.PAYPAL_CURRENCY or "USD").strip().upper()

    @property
    def app_base_url(self) -> str:
        return (self.APP_BASE_URL or "http://localhost:5173").strip().rstrip("/")

    @property
    def paypal_api_host(self) -> str:
        return (urlparse(self.PAYPAL_BASE_URL.strip()).hostname or "").lower()

    @property
    def paypal_is_sandbox(self) -> bool:
        parsed = urlparse(self.PAYPAL_BASE_URL.strip())
        return parsed.scheme == "https" and (parsed.hostname or "").lower() in PAYPAL_SANDBOX_HOSTS

    @property
    def paypal_credentials_configured(self) -> bool:
        return bool(self.PAYPAL_CLIENT_ID.strip() and self.PAYPAL_CLIENT_SECRET.strip())

    @property
    def openai_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY.strip())

    def __repr__(self) -> str:
        """Mask sensitive keys to prevent credential leakage in logs."""
        masked_openai = "***REDACTED***" if self.OPENAI_API_KEY else "not-set"
        masked_paypal_id = "***REDACTED***" if self.PAYPAL_CLIENT_ID else "not-set"
        masked_paypal_sec = "***REDACTED***" if self.PAYPAL_CLIENT_SECRET else "not-set"
        masked_app_secret = "***REDACTED***" if self.APP_SECRET_KEY else "not-set"

        return (
            f"Settings("
            f"DATABASE_URL='{self.DATABASE_URL}', "
            f"OPENAI_MODEL='{self.OPENAI_MODEL}', "
            f"PAYPAL_BASE_URL='{self.PAYPAL_BASE_URL}', "
            f"PAYPAL_CURRENCY='{self.currency}', "
            f"APP_BASE_URL='{self.app_base_url}', "
            f"CORS_ORIGINS='{self.CORS_ORIGINS}', "
            f"OPENAI_API_KEY='{masked_openai}', "
            f"PAYPAL_CLIENT_ID='{masked_paypal_id}', "
            f"PAYPAL_CLIENT_SECRET='{masked_paypal_sec}', "
            f"APP_SECRET_KEY='{masked_app_secret}')"
        )

    def __str__(self) -> str:
        return self.__repr__()


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
