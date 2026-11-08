"""Application configuration loaded from environment variables or .env file."""

from functools import lru_cache
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    APP_SECRET_KEY: str = "change-this-to-a-random-secret"
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a list of strings."""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return ["http://localhost:5173", "http://localhost:3000"]

    def __repr__(self) -> str:
        """Mask sensitive keys to prevent credential leakage in logs."""
        masked_openai = "***REDACTED***" if self.OPENAI_API_KEY else "not-set"
        masked_paypal_sec = "***REDACTED***" if self.PAYPAL_CLIENT_SECRET else "not-set"
        masked_app_secret = "***REDACTED***" if self.APP_SECRET_KEY else "not-set"

        return (
            f"Settings("
            f"DATABASE_URL='{self.DATABASE_URL}', "
            f"OPENAI_MODEL='{self.OPENAI_MODEL}', "
            f"PAYPAL_BASE_URL='{self.PAYPAL_BASE_URL}', "
            f"CORS_ORIGINS='{self.CORS_ORIGINS}', "
            f"OPENAI_API_KEY='{masked_openai}', "
            f"PAYPAL_CLIENT_ID='{self.PAYPAL_CLIENT_ID}', "
            f"PAYPAL_CLIENT_SECRET='{masked_paypal_sec}', "
            f"APP_SECRET_KEY='{masked_app_secret}')"
        )

    def __str__(self) -> str:
        return self.__repr__()


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
