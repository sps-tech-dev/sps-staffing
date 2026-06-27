"""Best-effort Idempotency-Key support for write endpoints (Part 31).

If the client sends an Idempotency-Key, the first successful create is cached in
Redis (24h) keyed by (tenant, key); a replay returns the same result instead of
creating a duplicate. Redis-unavailable degrades gracefully (the write proceeds).
"""
from __future__ import annotations

import json

from .db import get_redis

_TTL = 24 * 3600


def _k(tenant_id: str, key: str) -> str:
    return f"idem:{tenant_id}:{key}"


def get_cached(tenant_id: str, key: str | None) -> dict | None:
    if not key:
        return None
    try:
        raw = get_redis().get(_k(tenant_id, key))
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001 - idempotency is best-effort
        return None


def store(tenant_id: str, key: str | None, result: dict) -> None:
    if not key:
        return
    try:
        get_redis().set(_k(tenant_id, key), json.dumps(result), nx=True, ex=_TTL)
    except Exception:  # noqa: BLE001
        pass
