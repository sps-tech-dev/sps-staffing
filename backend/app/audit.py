"""Append-only audit writer (Part 18).

write_audit() inserts a shared.audit_logs row inside the caller's transaction
(the caller commits). NOTE: append-only is currently CONVENTION-ONLY — the
restricted INSERT-only DB role (no UPDATE/DELETE grants for the app role) is a
recorded pending item, not yet built. Do not assume DB-level immutability yet.
"""
from __future__ import annotations

import uuid

from .context import RequestContext
from .models import AuditLog


def write_audit(db, ctx: RequestContext, action: str, entity: str,
                entity_id: uuid.UUID | str | None = None,
                before: dict | None = None, after: dict | None = None) -> None:
    eid = uuid.UUID(str(entity_id)) if entity_id is not None else None
    db.add(AuditLog(
        tenant_id=uuid.UUID(str(ctx.tenant_id)),
        business_unit_id=ctx.business_unit_id or "STAFFING",
        actor_id=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None,
        action=action, entity=entity, entity_id=eid, before=before, after=after,
    ))
