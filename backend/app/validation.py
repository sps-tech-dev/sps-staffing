"""Reusable field validation + normalization (backend authority).

Single source of truth for email / Indian phone / PAN rules, used by Pydantic
request schemas across the API (login now; candidate registration etc. later).
The frontend mirrors these (lib/validation.ts) for UX, but the backend re-validates
— never trust the client.
"""
from __future__ import annotations

import re

# Email: requires a local part, '@', and a dotted domain (e.g. name@host.com).
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
# Indian mobile: exactly 10 digits starting 6-9, after stripping +91/0/spaces/dashes.
PHONE_RE = re.compile(r"^[6-9]\d{9}$")
# Indian PAN: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F).
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .,'&-]*$")
PINCODE_RE = re.compile(r"^\d{6}$")
_WEAK_PW = re.compile(r"^(password|passw0rd|12345678|qwerty|letmein|welcome)", re.IGNORECASE)


def validate_email(value: str) -> str:
    v = (value or "").strip().lower()
    if not EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address (e.g. name@example.com)")
    return v


def normalize_phone(value: str) -> str:
    """Strip +91 / leading 0 / spaces / dashes / parens; require a valid 10-digit mobile."""
    raw = re.sub(r"[\s\-()]", "", value or "")
    raw = re.sub(r"^(\+91|91|0)", "", raw)
    if not PHONE_RE.match(raw):
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return raw


def validate_pan(value: str) -> str:
    v = (value or "").strip().upper()
    if not PAN_RE.match(v):
        raise ValueError("Enter a valid PAN (5 letters, 4 digits, 1 letter — e.g. ABCDE1234F)")
    return v


# ── Common reusable checks (compose into request schemas) ────────
def required(value: str, label: str = "This field") -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{label} is required")
    return v


def validate_name(value: str) -> str:
    v = (value or "").strip()
    if not (2 <= len(v) <= 100) or not NAME_RE.match(v):
        raise ValueError("Enter a valid name (2-100 letters)")
    return v


def validate_password(value: str) -> str:
    if len(value or "") < 12:
        raise ValueError("Password must be at least 12 characters")
    if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
        raise ValueError("Password must include at least one letter and one number")
    if _WEAK_PW.match(value):
        raise ValueError("Password is too weak")
    return value


def validate_pincode(value: str) -> str:
    v = (value or "").strip()
    if not PINCODE_RE.match(v):
        raise ValueError("Enter a valid 6-digit PIN code")
    return v

