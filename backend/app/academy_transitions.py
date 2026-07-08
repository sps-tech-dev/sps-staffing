"""8b-1 — academy enrolment status transition machine: the SINGLE authority for
`enrollment.status` moves. Every edge is tagged system|manual. Machine-enforced
invariants (fail closed, not endpoint convention):
  - a move not in the table → rejected.
  - a [system] edge requested by a manual caller → rejected (so a manual move can
    NEVER reach 'active' — offered→active is system-only, the activation seam's job).
  - a move FROM a terminal state → rejected for ANY caller (explicit terminal-set
    check, so a future careless table edit can't open an out-edge from terminal).
  - a manual move REQUIRES a reason.
Every successful move emits an `academy.enrollment.transition` audit — the status-
transition trail that did NOT exist before 8b-1 (finding #6). No new table: reuses
the existing write_audit / shared.audit_logs mechanism.

`applied→tested` is DELIBERATELY absent: no writer performs it (dead vocabulary).
The grade writes 'offered' in one step; 'tested' has no code ingress (seed-only),
and the grade advances it OUT via tested→offered if a seed ever set it.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .audit import write_audit
from .context import RequestContext

# (from, to) → kind. NOTHING else is legal.
_EDGES: dict[tuple[str, str], str] = {
    ("applied", "offered"): "system",     # grade
    ("tested", "offered"): "system",      # grade (only reachable when a seed set 'tested')
    ("offered", "active"): "system",      # pay / activation seam ONLY
    ("offered", "cancelled"): "manual",   # 8b-2
    ("applied", "cancelled"): "manual",   # 8b-2
    ("tested", "cancelled"): "manual",    # 8b-2
    ("active", "completed"): "manual",    # 8b-2 / future
    ("active", "dropped"): "manual",      # 8b-2
}
# Terminal states — checked EXPLICITLY (not merely by absence of an out-row).
TERMINAL: frozenset[str] = frozenset({"cancelled", "dropped", "completed"})


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def transition(db: Session, enrollment, to_state: str, *, kind: str,
               reason: str | None = None, actor: str = "system",
               ctx: RequestContext | None = None) -> None:
    """Perform ONE guarded status transition + emit the transition audit. The caller
    commits. `kind` ∈ {'system','manual'}."""
    if kind not in ("system", "manual"):
        raise _err(422, "VALIDATION_ERROR", "kind must be 'system' or 'manual'")
    src = enrollment.status

    # 1. terminal source — explicit set check, fail closed
    if src in TERMINAL:
        raise _err(409, "ILLEGAL_TRANSITION", f"'{src}' is terminal — no transitions out")
    # 2. the edge must exist in the table
    edge_kind = _EDGES.get((src, to_state))
    if edge_kind is None:
        raise _err(409, "ILLEGAL_TRANSITION", f"Cannot move {src} → {to_state}")
    # 3. a [system] edge cannot be traversed by a manual caller (machine-enforced) —
    #    this is what structurally forbids a manual move from reaching 'active'
    if edge_kind == "system" and kind != "system":
        raise _err(409, "ILLEGAL_TRANSITION",
                   f"{src} → {to_state} is a system transition — not permitted for a manual move")
    # 4. manual moves require a reason
    if kind == "manual" and not (reason and reason.strip()):
        raise _err(422, "REASON_REQUIRED", "A reason is required for a manual status change")

    # 5. perform + audit (one audit row per successful transition)
    audit_ctx = ctx or RequestContext(tenant_id=str(enrollment.tenant_id),
                                      business_unit_id="ACADEMY", user_id=None, roles=())
    enrollment.status = to_state
    write_audit(db, audit_ctx, "academy.enrollment.transition", "enrollment", enrollment.id,
                after={"enrollment_id": str(enrollment.id), "from": src, "to": to_state,
                       "kind": kind, "reason": reason.strip() if reason else None, "actor": actor})
