"""
FastAPI REST Layer Package (`src.api`).

Exposes HTTP endpoints for credit card transfer optimization, flight crediting simulation,
and alliance reference data lookups.
"""

from src.api.main import create_app

__all__ = ["create_app"]
