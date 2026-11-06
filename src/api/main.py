"""
FastAPI Application Factory & Middleware Skeleton (`src/api/main.py`).

Provides the ASGI application factory and healthcheck endpoint while outlining
Phase 2 tasks for router registration, CORS configuration, database lifespan management,
and RFC 7807 structured error handling.
"""

from typing import Any


def create_app() -> Any:
    """
    Constructs and configures the FastAPI application instance.

    # TODO (Phase 2 - FastAPI Initialization):
    # 1. Instantiate `FastAPI(title="Loyalty Arbitrage Engine API", version="0.2.0", lifespan=lifespan)`.
    # 2. Configure `CORSMiddleware` with environment-specific allowed origins.
    # 3. Register custom exception handlers for `ValueError` (HTTP 422) and `KeyError` (HTTP 404).
    # 4. Mount `src.api.routes.router` under the `/api/v1` prefix.
    """
    raise NotImplementedError("TODO: Implement in Phase 2")


def healthcheck() -> dict[str, str]:
    """
    Lightweight readiness probe for container orchestrators and AWS API Gateway.

    # TODO (Phase 2 - Healthcheck):
    # - Add optional database ping latency metric (`db_status: "connected"`).
    """
    return {
        "status": "ok",
        "service": "loyalty-arbitrage-engine",
        "phase": "phase-1-core-scaffold",
    }
