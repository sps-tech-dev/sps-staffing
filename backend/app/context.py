from contextvars import ContextVar
from dataclasses import dataclass

@dataclass
class RequestContext:
    tenant_id: str
    business_unit_id: str | None
    user_id: str | None = None
    roles: tuple[str, ...] = ()
    # Client-portal sub-scope (nested inside tenant). Set ONLY for an active client
    # portal session (from the JWT). When present, the base repository additionally
    # filters every query by client_id — a client can read only its own company's rows.
    client_id: str | None = None
    # Client-internal role for the session: 'client_admin' (HR — all client jobs) or
    # 'client_manager' (own posted jobs only). Drives owner-scoping + the offer-write gate.
    client_role: str | None = None

_ctx: ContextVar[RequestContext | None] = ContextVar("ctx", default=None)

def set_context(c: RequestContext) -> None: _ctx.set(c)
def get_context() -> RequestContext:
    c = _ctx.get()
    if c is None:
        raise RuntimeError("request context not set")
    return c

# Vertical path segment -> business unit
VERTICAL = {
    "staffing-and-recruitment": "STAFFING",
    "training-and-internship": "ACADEMY",
    "it-services-and-consulting": "CONSULTING",
}
# Non-tenant labels: infra/app hosts that map to the owner tenant, not a tenant
# slug. Includes the per-environment API hosts (e.g. dev-api / staging-api) so the
# deployed single-tenant API resolves to the owner until real tenant subdomains +
# CloudFront exist (the deferred Host↔JWT work).
RESERVED_SUBDOMAINS = {
    "www", "api", "auth", "app", "admin", "static", "cdn", "mail",
    "dev", "dev-api", "staging", "staging-api", "uat", "uat-api",
}

def tenant_from_host(host: str, base_domain: str) -> str:
    h = host.split(":")[0].removeprefix("www.")
    labels = h.split(".")
    if h == base_domain or len(labels) <= base_domain.count(".") + 1:
        return "sps"                      # apex -> owner tenant
    sub = labels[0]
    return "sps" if sub in RESERVED_SUBDOMAINS else sub
