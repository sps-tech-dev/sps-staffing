"""Read-models for dashboards. Computed from real, tenant-scoped DB rows.

Slice 2 ships the candidate overview. With no staffing tables yet (those arrive
in Slice 3 / migration 0004), activity counts are genuinely 0 and `recent` is
empty — the real state of a brand-new candidate. profileComplete is derived from
the user's actual fields. Slice 3 fills counts/recent from staffing.applications.
"""
from __future__ import annotations

import uuid

from .context import RequestContext
from .models import User
from .repositories import TenantScopedRepo


def candidate_overview(db, ctx: RequestContext) -> dict:
    repo = TenantScopedRepo(db, ctx)
    q = repo.base_query(User).where(User.id == uuid.UUID(str(ctx.user_id)))
    user = db.execute(q).scalar_one_or_none()

    filled = [
        bool(user and user.full_name),
        bool(user and user.email),
        bool(user and user.status == "active"),
    ]
    profile_complete = round(100 * sum(filled) / len(filled)) if user else 0

    return {
        # TODO(Slice 3): count from staffing.applications scoped to this candidate.
        "applications": 0,
        "interviews": 0,
        "offers": 0,
        "profileComplete": profile_complete,
        "recent": [],  # TODO(Slice 3): recent applications
    }
