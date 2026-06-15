from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TransactionKind(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"


class TransactionStatus(str, enum.Enum):
    POSTED = "posted"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    wallets: Mapped[list[Wallet]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="user", foreign_keys="Transaction.user_id", cascade="all, delete-orphan"
    )


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("user_id", "currency", name="uq_wallet_user_currency"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="wallets")


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        Index("ix_exchange_latest", "currency", "fetched_at"),
        UniqueConstraint("provider", "base_currency", "currency", "fetched_at", name="uq_exchange_snapshot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_transaction_idempotency"),
        Index("ix_transactions_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    wallet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wallets.id"), nullable=True)
    counterparty_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    related_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    exchange_rate_id: Mapped[Optional[int]] = mapped_column(ForeignKey("exchange_rates.id"), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    kind: Mapped[TransactionKind] = mapped_column(Enum(TransactionKind), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus), default=TransactionStatus.POSTED, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    wallet_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    wallet_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    exchange_rate_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exchange_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    exchange_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="transactions", foreign_keys=[user_id])
