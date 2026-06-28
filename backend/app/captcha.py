"""hCaptcha verification for the public registration bot gate.

Two modes (see config):
- HCAPTCHA_SECRET set  → real server-side verification against hCaptcha's
  siteverify endpoint.
- HCAPTCHA_SECRET empty → LOCAL test mode: any NON-EMPTY token passes (no network
  call), so the gate mechanism (missing token → reject) is still exercised in the
  local loop + tests. Provisioning real keys is STOP-4 (hCaptcha account).
"""
from __future__ import annotations

import urllib.parse
import urllib.request

from .config import settings

_SITEVERIFY = "https://hcaptcha.com/siteverify"


def verify_captcha(token: str | None) -> bool:
    if not token:
        return False
    if not settings.hcaptcha_secret:
        return True  # local/test mode: token present is enough (no external call)
    try:
        data = urllib.parse.urlencode({"secret": settings.hcaptcha_secret, "response": token}).encode()
        with urllib.request.urlopen(_SITEVERIFY, data=data, timeout=5) as resp:  # noqa: S310
            import json
            return bool(json.loads(resp.read().decode()).get("success"))
    except Exception:  # noqa: BLE001 — verification failure = reject, never 500 the signup
        return False
