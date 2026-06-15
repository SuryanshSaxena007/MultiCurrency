from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_session
from app.models import Transaction, TransactionKind, User, Wallet
from app.schemas import MoneyRequest, TransactionPage, TransactionResponse, TransferRequest, WalletResponse
from app.services.wallet_service import credit_wallet, debit_wallet, transfer_funds

router = APIRouter(tags=["wallets"])


@router.get("/wallets", response_model=list[WalletResponse])
def list_wallets(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[WalletResponse]:
    wallets = session.scalars(select(Wallet).where(Wallet.user_id == current_user.id).order_by(Wallet.currency)).all()
    return [WalletResponse.model_validate(wallet) for wallet in wallets]


@router.post("/wallets/credit", response_model=TransactionResponse)
def credit(
    payload: MoneyRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> TransactionResponse:
    _, transaction = credit_wallet(session, current_user, payload)
    session.commit()
    session.refresh(transaction)
    return TransactionResponse.model_validate(transaction)


@router.post("/wallets/debit", response_model=TransactionResponse)
def debit(
    payload: MoneyRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> TransactionResponse:
    _, transaction = debit_wallet(session, current_user, payload)
    session.commit()
    session.refresh(transaction)
    return TransactionResponse.model_validate(transaction)


@router.post("/transfers", response_model=TransactionResponse)
def transfer(
    payload: TransferRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> TransactionResponse:
    _, _, transaction = transfer_funds(session, current_user, payload)
    session.commit()
    session.refresh(transaction)
    return TransactionResponse.model_validate(transaction)


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    kind: Optional[TransactionKind] = None,
    currency: Optional[str] = Query(default=None, min_length=3, max_length=3),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> TransactionPage:
    filters = [Transaction.user_id == current_user.id]
    if kind is not None:
        filters.append(Transaction.kind == kind)
    if currency is not None:
        filters.append(Transaction.currency == currency.upper())
    if start_date is not None:
        filters.append(Transaction.created_at >= start_date)
    if end_date is not None:
        filters.append(Transaction.created_at <= end_date)

    total = session.scalar(select(func.count()).select_from(Transaction).where(*filters)) or 0
    transactions = session.scalars(
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TransactionPage(
        items=[TransactionResponse.model_validate(transaction) for transaction in transactions],
        page=page,
        page_size=page_size,
        total=total,
    )
