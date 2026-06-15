from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "INR", "AUD", "CAD", "JPY"}


def normalise_currency(value: str) -> str:
    currency = value.strip().upper()
    if currency not in SUPPORTED_CURRENCIES:
        supported = ", ".join(sorted(SUPPORTED_CURRENCIES))
        raise ValueError(f"Unsupported currency '{currency}'. Supported currencies: {supported}")
    return currency


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    default_currency: str = "USD"
    photo_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("default_currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalise_currency(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    photo_url: Optional[str]
    default_currency: str
    created_at: datetime


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    photo_url: Optional[str] = Field(default=None, max_length=500)
    default_currency: Optional[str] = None

    @field_validator("default_currency")
    @classmethod
    def validate_optional_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalise_currency(value)


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    currency: str
    balance: Decimal
    version: int
    updated_at: datetime


class MoneyRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"), decimal_places=2, max_digits=18)
    currency: str
    wallet_currency: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=100)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalise_currency(value)

    @field_validator("wallet_currency")
    @classmethod
    def validate_wallet_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalise_currency(value)


class TransferRequest(BaseModel):
    recipient_email: EmailStr
    amount: Decimal = Field(gt=Decimal("0"), decimal_places=2, max_digits=18)
    currency: str
    source_wallet_currency: Optional[str] = None
    target_wallet_currency: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=100)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalise_currency(value)

    @field_validator("source_wallet_currency", "target_wallet_currency")
    @classmethod
    def validate_optional_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalise_currency(value)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    amount: Decimal
    currency: str
    wallet_currency: str
    wallet_amount: Decimal
    exchange_rate_value: Decimal
    exchange_provider: str
    exchange_fetched_at: datetime
    counterparty_id: Optional[int]
    related_transaction_id: Optional[int]
    description: Optional[str]
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionResponse]
    page: int
    page_size: int
    total: int


class RateResponse(BaseModel):
    currency: str
    rate: Decimal
    provider: str
    fetched_at: datetime


class QuoteResponse(BaseModel):
    source_amount: Decimal
    source_currency: str
    target_amount: Decimal
    target_currency: str
    exchange_rate_value: Decimal
    provider: str
    fetched_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
