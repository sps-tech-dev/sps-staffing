"""Lazy data-tier clients.

Nothing here connects at import time. The SQLAlchemy engine and Redis client
are created on FIRST USE only (get_engine / get_redis), and even creating the
engine does not open a connection — that happens when a connection is checked
out (e.g. in check_db). This keeps app startup dependency-free so the ECS
health check (/healthz) never depends on RDS/Redis being reachable.
"""
from __future__ import annotations

from .config import settings

_engine = None
_redis = None


def get_engine():
    """SQLAlchemy engine, created once on first use. create_engine() itself
    does NOT connect; short connect timeout so checks fail fast, never hang."""
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=2,
            connect_args={"connect_timeout": 3},
        )
    return _engine


def get_redis():
    """Redis client, created once on first use. Construction does not connect;
    short socket timeouts so a PING fails fast rather than hanging."""
    global _redis
    if _redis is None:
        import redis
        _redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
    return _redis


def check_db() -> None:
    """Lightweight liveness check: SELECT 1. Raises on failure."""
    from sqlalchemy import text
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))


def check_redis() -> None:
    """Lightweight liveness check: PING. Raises on failure."""
    get_redis().ping()
