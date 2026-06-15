from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_session
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="wallet-api")


@router.get("/ready", response_model=HealthResponse)
def ready(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    session.execute(text("select 1"))
    return HealthResponse(status="ready", service="wallet-api")


@router.get("/metrics")
def metrics(request: Request) -> Response:
    counters: dict[str, int] = request.app.state.status_counters
    lines = ["# HELP wallet_http_responses_total HTTP responses by status class", "# TYPE wallet_http_responses_total counter"]
    for bucket in sorted(counters):
        lines.append(f'wallet_http_responses_total{{status_class="{bucket}"}} {counters[bucket]}')
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
