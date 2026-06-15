from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, exchange, health, profile, wallets
from app.config import Settings, get_settings
from app.database import build_engine, build_session_factory, init_db
from app.exchange import refresh_exchange_rates, seed_default_rates

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("wallet")


async def exchange_refresh_loop(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    while True:
        await asyncio.sleep(settings.exchange_refresh_seconds)
        session = app.state.session_factory()
        try:
            await refresh_exchange_rates(session, settings)
        except Exception as exc:
            session.rollback()
            logger.warning("exchange_refresh_failed", extra={"error": str(exc)})
        finally:
            session.close()


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(app_settings.database_url)
        session_factory = build_session_factory(engine)
        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.status_counters = defaultdict(int)
        init_db(engine)
        seed_session = session_factory()
        try:
            seed_default_rates(seed_session, app_settings)
        finally:
            seed_session.close()
        refresh_task: Optional[asyncio.Task[None]] = None
        if app_settings.enable_external_rates:
            refresh_task = asyncio.create_task(exchange_refresh_loop(app))
        try:
            yield
        finally:
            if refresh_task is not None:
                refresh_task.cancel()
                try:
                    await refresh_task
                except asyncio.CancelledError:
                    logger.info("exchange_refresh_stopped")
            engine.dispose()

    app = FastAPI(title=app_settings.app_name, version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_and_count(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        bucket = f"{response.status_code // 100}xx"
        request.app.state.status_counters[bucket] += 1
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": elapsed_ms,
                }
            )
        )
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(wallets.router)
    app.include_router(exchange.router)
    return app


app = create_app()
