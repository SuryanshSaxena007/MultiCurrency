from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exchange import ConversionQuote, convert, quantize_money
from app.models import Transaction, TransactionKind, TransactionStatus, User, Wallet
from app.schemas import MoneyRequest, TransferRequest, normalise_currency


def get_or_create_wallet(session: Session, user_id: int, currency: str, lock: bool = False) -> Wallet:
    currency_code = normalise_currency(currency)
    statement = select(Wallet).where(Wallet.user_id == user_id, Wallet.currency == currency_code)
    if lock:
        statement = statement.with_for_update()
    wallet = session.scalar(statement)
    if wallet is not None:
        return wallet
    wallet = Wallet(user_id=user_id, currency=currency_code, balance=Decimal("0.00"))
    session.add(wallet)
    session.flush()
    return wallet


def get_idempotent_transaction(session: Session, user_id: int, idempotency_key: Optional[str]) -> Optional[Transaction]:
    if idempotency_key is None:
        return None
    return session.scalar(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.idempotency_key == idempotency_key).limit(1)
    )


def build_transaction(
    *,
    user: User,
    wallet: Wallet,
    kind: TransactionKind,
    request_amount: Decimal,
    request_currency: str,
    wallet_amount: Decimal,
    quote: ConversionQuote,
    description: Optional[str],
    idempotency_key: Optional[str],
    counterparty_id: Optional[int] = None,
) -> Transaction:
    return Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        counterparty_id=counterparty_id,
        exchange_rate_id=quote.rate_id,
        idempotency_key=idempotency_key,
        kind=kind,
        status=TransactionStatus.POSTED,
        amount=quantize_money(request_amount),
        currency=request_currency,
        wallet_currency=wallet.currency,
        wallet_amount=wallet_amount,
        exchange_rate_value=quote.exchange_rate_value,
        exchange_provider=quote.provider,
        exchange_fetched_at=quote.fetched_at,
        description=description,
    )


def require_positive_wallet_amount(amount: Decimal) -> None:
    if amount <= Decimal("0.00"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Converted wallet amount is too small")


def credit_wallet(session: Session, user: User, payload: MoneyRequest) -> tuple[Wallet, Transaction]:
    existing = get_idempotent_transaction(session, user.id, payload.idempotency_key)
    if existing is not None:
        wallet = get_or_create_wallet(session, user.id, existing.wallet_currency)
        return wallet, existing

    wallet_currency = payload.wallet_currency or user.default_currency
    quote = convert(session, payload.amount, payload.currency, wallet_currency)
    require_positive_wallet_amount(quote.target_amount)
    wallet = get_or_create_wallet(session, user.id, wallet_currency, lock=True)
    wallet.balance = quantize_money(wallet.balance + quote.target_amount)
    wallet.version += 1
    transaction = build_transaction(
        user=user,
        wallet=wallet,
        kind=TransactionKind.CREDIT,
        request_amount=payload.amount,
        request_currency=payload.currency,
        wallet_amount=quote.target_amount,
        quote=quote,
        description=payload.description,
        idempotency_key=payload.idempotency_key,
    )
    session.add(transaction)
    session.flush()
    return wallet, transaction


def debit_wallet(session: Session, user: User, payload: MoneyRequest) -> tuple[Wallet, Transaction]:
    existing = get_idempotent_transaction(session, user.id, payload.idempotency_key)
    if existing is not None:
        wallet = get_or_create_wallet(session, user.id, existing.wallet_currency)
        return wallet, existing

    wallet_currency = payload.wallet_currency or user.default_currency
    quote = convert(session, payload.amount, payload.currency, wallet_currency)
    require_positive_wallet_amount(quote.target_amount)
    wallet = get_or_create_wallet(session, user.id, wallet_currency, lock=True)
    if wallet.balance < quote.target_amount:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient wallet balance")
    wallet.balance = quantize_money(wallet.balance - quote.target_amount)
    wallet.version += 1
    transaction = build_transaction(
        user=user,
        wallet=wallet,
        kind=TransactionKind.DEBIT,
        request_amount=payload.amount,
        request_currency=payload.currency,
        wallet_amount=-quote.target_amount,
        quote=quote,
        description=payload.description,
        idempotency_key=payload.idempotency_key,
    )
    session.add(transaction)
    session.flush()
    return wallet, transaction


def transfer_funds(session: Session, sender: User, payload: TransferRequest) -> tuple[Wallet, Wallet, Transaction]:
    existing = get_idempotent_transaction(session, sender.id, payload.idempotency_key)
    if existing is not None:
        sender_wallet = get_or_create_wallet(session, sender.id, existing.wallet_currency)
        if existing.counterparty_id is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key reused for incompatible operation")
        recipient = session.get(User, existing.counterparty_id)
        if recipient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")
        recipient_wallet = get_or_create_wallet(session, recipient.id, payload.target_wallet_currency or recipient.default_currency)
        return sender_wallet, recipient_wallet, existing

    recipient = session.scalar(select(User).where(User.email == str(payload.recipient_email).lower()))
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")
    if recipient.id == sender.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer to yourself")

    source_wallet_currency = payload.source_wallet_currency or sender.default_currency
    target_wallet_currency = payload.target_wallet_currency or recipient.default_currency
    debit_quote = convert(session, payload.amount, payload.currency, source_wallet_currency)
    credit_quote = convert(session, payload.amount, payload.currency, target_wallet_currency)
    require_positive_wallet_amount(debit_quote.target_amount)
    require_positive_wallet_amount(credit_quote.target_amount)

    sender_wallet = get_or_create_wallet(session, sender.id, source_wallet_currency, lock=True)
    recipient_wallet = get_or_create_wallet(session, recipient.id, target_wallet_currency, lock=True)
    if sender_wallet.balance < debit_quote.target_amount:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient wallet balance")

    sender_wallet.balance = quantize_money(sender_wallet.balance - debit_quote.target_amount)
    sender_wallet.version += 1
    recipient_wallet.balance = quantize_money(recipient_wallet.balance + credit_quote.target_amount)
    recipient_wallet.version += 1

    transfer_out = build_transaction(
        user=sender,
        wallet=sender_wallet,
        kind=TransactionKind.TRANSFER_OUT,
        request_amount=payload.amount,
        request_currency=payload.currency,
        wallet_amount=-debit_quote.target_amount,
        quote=debit_quote,
        description=payload.description,
        idempotency_key=payload.idempotency_key,
        counterparty_id=recipient.id,
    )
    transfer_in = build_transaction(
        user=recipient,
        wallet=recipient_wallet,
        kind=TransactionKind.TRANSFER_IN,
        request_amount=payload.amount,
        request_currency=payload.currency,
        wallet_amount=credit_quote.target_amount,
        quote=credit_quote,
        description=payload.description,
        idempotency_key=None,
        counterparty_id=sender.id,
    )
    session.add_all([transfer_out, transfer_in])
    session.flush()
    transfer_out.related_transaction_id = transfer_in.id
    transfer_in.related_transaction_id = transfer_out.id
    session.flush()
    return sender_wallet, recipient_wallet, transfer_out
