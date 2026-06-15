from decimal import Decimal
from typing import Annotated, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_current_user, get_session, get_settings_from_app
from app.exchange import convert, latest_rate, refresh_exchange_rates
from app.models import ExchangeRate, User
from app.schemas import QuoteResponse, RateResponse, normalise_currency

router = APIRouter(prefix="/exchange", tags=["exchange"])


@router.get("/rates", response_model=list[RateResponse])
def list_rates(
    _: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[RateResponse]:
    currencies = session.scalars(select(ExchangeRate.currency).distinct().order_by(ExchangeRate.currency)).all()
    return [
        RateResponse(
            currency=rate.currency,
            rate=rate.rate,
            provider=rate.provider,
            fetched_at=rate.fetched_at,
        )
        for rate in (latest_rate(session, currency) for currency in currencies)
    ]


@router.post("/refresh")
async def refresh_rates(
    _: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_from_app)],
) -> dict[str, Union[int, str]]:
    try:
        count = await refresh_exchange_rates(session, settings)
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Exchange provider unavailable") from exc
    return {"status": "refreshed", "count": count}


@router.get("/quote", response_model=QuoteResponse)
def quote(
    _: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    amount: Decimal = Query(gt=Decimal("0")),
    source_currency: str = Query(min_length=3, max_length=3),
    target_currency: str = Query(min_length=3, max_length=3),
) -> QuoteResponse:
    quote_result = convert(session, amount, normalise_currency(source_currency), normalise_currency(target_currency))
    return QuoteResponse(
        source_amount=quote_result.source_amount,
        source_currency=quote_result.source_currency,
        target_amount=quote_result.target_amount,
        target_currency=quote_result.target_currency,
        exchange_rate_value=quote_result.exchange_rate_value,
        provider=quote_result.provider,
        fetched_at=quote_result.fetched_at,
    )
