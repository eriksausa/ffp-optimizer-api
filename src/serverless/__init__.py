"""
Serverless Deployment Layer Package (`src.serverless`).

Adapts the FastAPI ASGI application and background promotional rate-refresh jobs
for AWS Lambda + API Gateway and Amazon EventBridge.
"""

from src.serverless.lambda_handler import api_gateway_handler, scheduled_bonus_refresh_handler

__all__ = ["api_gateway_handler", "scheduled_bonus_refresh_handler"]
