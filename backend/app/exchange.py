from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ExchangeRate
from app.schemas import normalise_currency

logger = logging.getLogger(__name__)

MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.00000001")
DEFAULT_USD_RATES = {
    "USD": Decimal("1.00000000"),
    "EUR": Decimal("0.92000000"),
    "GBP": Decimal("0.79000000"),
    "INR": Decimal("83.00000000"),
    "AUD": Decimal("1.51000000"),
    "CAD": Decimal("1.36000000"),
    "JPY": Decimal("156.00000000"),
}


@dataclass(frozen=True)
class RateSnapshot:
    currency: str
    rate: Decimal
    provider: str
    fetched_at: datetime
    rate_id: Optional[int]


@dataclass(frozen=True)
class ConversionQuote:
    source_amount: Decimal
    source_currency: str
    target_amount: Decimal
    target_currency: str
    exchange_rate_value: Decimal
    provider: str
    fetched_at: datetime
    rate_id: Optional[int]


class ExchangeProvider:
    name = "frankfurter"

    async def fetch_usd_rates(self, settings: Settings) -> dict[str, Decimal]:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(settings.exchange_provider_url)
            response.raise_for_status()
            payload = response.json()
        raw_rates = payload.get("rates")
        if not isinstance(raw_rates, dict):
            raise ValueError("Exchange provider response missing rates")
        rates = {"USD": Decimal("1.00000000")}
        supported = settings.supported_currency_set
        for currency, value in raw_rates.items():
            currency_code = str(currency).upper()
            if currency_code in supported:
                rates[currency_code] = Decimal(str(value)).quantize(RATE_QUANT)
        missing = supported.difference(rates)
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"Exchange provider missing rates for: {missing_list}")
        return rates


def quantize_money(amount: Decimal) -> Decimal:
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def quantize_rate(rate: Decimal) -> Decimal:
    return rate.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)


def seed_default_rates(session: Session, settings: Settings) -> None:
    existing_count = session.scalar(select(ExchangeRate.id).limit(1))
    if existing_count is not None:
        return

    fetched_at = datetime.now(timezone.utc)
    supported = settings.supported_currency_set
    for currency, rate in DEFAULT_USD_RATES.items():
        if currency in supported:
            session.add(
                ExchangeRate(
                    provider="seed",
                    base_currency="USD",
                    currency=currency,
                    rate=rate,
                    fetched_at=fetched_at,
                )
            )
    session.commit()


async def refresh_exchange_rates(session: Session, settings: Settings, provider: Optional[ExchangeProvider] = None) -> int:
    if not settings.enable_external_rates:
        return 0
    exchange_provider = provider or ExchangeProvider()
    rates = await exchange_provider.fetch_usd_rates(settings)
    fetched_at = datetime.now(timezone.utc)
    for currency, rate in rates.items():
        normalise_currency(currency)
        session.add(
            ExchangeRate(
                provider=exchange_provider.name,
                base_currency="USD",
                currency=currency,
                rate=quantize_rate(rate),
                fetched_at=fetched_at,
            )
        )
    session.commit()
    logger.info("exchange_rates_refreshed", extra={"provider": exchange_provider.name, "count": len(rates)})
    return len(rates)


def latest_rate(session: Session, currency: str) -> RateSnapshot:
    currency_code = normalise_currency(currency)
    rate = session.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.currency == currency_code)
        .order_by(ExchangeRate.fetched_at.desc(), ExchangeRate.id.desc())
        .limit(1)
    )
    if rate is None:
        fallback = DEFAULT_USD_RATES[currency_code]
        return RateSnapshot(
            currency=currency_code,
            rate=fallback,
            provider="fallback",
            fetched_at=datetime.now(timezone.utc),
            rate_id=None,
        )
    return RateSnapshot(
        currency=rate.currency,
        rate=Decimal(rate.rate),
        provider=rate.provider,
        fetched_at=rate.fetched_at,
        rate_id=rate.id,
    )


def convert(session: Session, amount: Decimal, source_currency: str, target_currency: str) -> ConversionQuote:
    source_code = normalise_currency(source_currency)
    target_code = normalise_currency(target_currency)
    source = latest_rate(session, source_code)
    target = latest_rate(session, target_code)
    cross_rate = quantize_rate(target.rate / source.rate)
    target_amount = quantize_money(amount * cross_rate)
    return ConversionQuote(
        source_amount=quantize_money(amount),
        source_currency=source_code,
        target_amount=target_amount,
        target_currency=target_code,
        exchange_rate_value=cross_rate,
        provider=target.provider if target.provider != "fallback" else source.provider,
        fetched_at=target.fetched_at if target.provider != "fallback" else source.fetched_at,
        rate_id=target.rate_id or source.rate_id,
    )
