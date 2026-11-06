"""
PostgreSQL Persistence Layer Package (`src.db`).

Provides async SQLAlchemy 2.0 session management and repository classes for storing
transfer partner matrices, temporal earning rules, and award sweet-spot benchmarks.
"""

from src.db.session import DatabaseSessionManager, get_db_session
from src.db.repository import LoyaltyRepository

__all__ = ["DatabaseSessionManager", "get_db_session", "LoyaltyRepository"]
