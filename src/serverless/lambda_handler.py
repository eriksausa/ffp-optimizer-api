"""
AWS Lambda Entry Point & EventBridge Scheduled Handler Skeleton (`src/serverless/lambda_handler.py`).

Architectural Notes:
- Uses `Mangum` to wrap the FastAPI ASGI app for AWS API Gateway HTTP/REST proxy events.
- Provides a separate handler for Amazon EventBridge scheduled cron events (`rate(12 hours)`)
  to refresh promotional credit card transfer bonuses into PostgreSQL without blocking API requests.
"""

from typing import Any


def api_gateway_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Primary AWS Lambda handler for API Gateway proxy requests.

    # TODO (Phase 2 - Mangum ASGI Wrapper):
    # 1. Import `Mangum` from `mangum` and `create_app` from `src.api.main`.
    # 2. Initialize the ASGI app outside the handler for warm-start reuse across invocations.
    # 3. Configure `Mangum(app, lifespan="off")` when using RDS Proxy / external connection pooling.
    # 4. Delegate `(event, context)` to the Mangum instance and return the proxy response dict.
    """
    raise NotImplementedError("TODO: Implement in Phase 2")


def scheduled_bonus_refresh_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler triggered by Amazon EventBridge (`cron(0 */12 * * ? *)`) to sync
    promotional bank transfer bonuses (e.g., Chase -> Iberia Avios 30% bonus) into PostgreSQL.

    # TODO (Phase 2 - Scheduled Ingestion Job):
    # 1. Instantiate `ExternalIngestionClient` from `src.core.ingestion_client`.
    # 2. Fetch active promotional bonuses via `fetch_active_bank_transfer_bonuses()`.
    # 3. Upsert updated bonus percentages into PostgreSQL via `LoyaltyRepository.upsert_transfer_bonus`.
    # 4. Return structured execution summary (`{"updated_rules_count": ..., "status": "success"}`).
    """
    raise NotImplementedError("TODO: Implement in Phase 2")
