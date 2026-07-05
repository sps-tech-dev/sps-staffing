"""Password hashing (argon2) + JWT issue/verify. No DB access here."""
from __future__ import annotations

import datetime as dt

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt

from .config import settings

_ph = PasswordHasher()
ALG = "HS256"


def hash_password(password: str) -> str:
    """argon2 hash for a new credential (e.g. on client-account activation)."""
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """True iff the password matches. The seeded sentinel '!' (not a valid argon2
    hash) raises InvalidHashError → returns False, so an un-activated account
    cannot log in."""
    try:
        _ph.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def _create(claims: dict, secret: str, ttl_seconds: int, token_type: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        **claims,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=ttl_seconds)).timestamp()),
        "type": token_type,
    }
    return jwt.encode(payload, secret, algorithm=ALG)


def create_access_token(claims: dict) -> str:
    return _create(claims, settings.jwt_access_secret, settings.access_ttl_seconds, "access")


def create_refresh_token(claims: dict) -> str:
    return _create(claims, settings.jwt_refresh_secret, settings.refresh_ttl_seconds, "refresh")


def decode_access_token(token: str) -> dict | None:
    return _decode(token, settings.jwt_access_secret, "access")


def decode_refresh_token(token: str) -> dict | None:
    return _decode(token, settings.jwt_refresh_secret, "refresh")


def create_academy_token(claims: dict) -> str:
    """A3 — academy-student access token. DISTINCT secret + DISTINCT type from the
    staffing access token, so the two are non-interchangeable both cryptographically
    (secret) and by claim (type='academy_access')."""
    return _create(claims, settings.jwt_academy_secret, settings.access_ttl_seconds, "academy_access")


def decode_academy_token(token: str) -> dict | None:
    return _decode(token, settings.jwt_academy_secret, "academy_access")


def _decode(token: str, secret: str, token_type: str) -> dict | None:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALG])
    except JWTError:
        return None
    if payload.get("type") != token_type:
        return None
    return payload
