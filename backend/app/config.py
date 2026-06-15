from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="WALLET_", extra="ignore")

    app_name: str = "Multi-Currency Wallet"
    environment: str = "development"
    database_url: str = "sqlite:///./wallet.db"
    jwt_secret: str = Field(default="change-me-in-production", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,http://localhost:3000"
    supported_currencies: str = "USD,EUR,GBP,INR,AUD,CAD,JPY"
    exchange_provider_url: str = "https://api.frankfurter.app/latest?from=USD"
    exchange_refresh_seconds: int = 3600
    enable_external_rates: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgres_url(cls, value: str) -> str:
        if value and value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supported_currency_set(self) -> set[str]:
        return {currency.strip().upper() for currency in self.supported_currencies.split(",") if currency.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
