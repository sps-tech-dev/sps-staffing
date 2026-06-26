from contextvars import ContextVar
from dataclasses import dataclass

@dataclass
class RequestContext:
    tenant_id: str
    business_unit_id: str | None
    user_id: str | None = None
    roles: tuple[str, ...] = ()

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
RESERVED_SUBDOMAINS = {"www", "api", "auth", "app", "admin", "static", "cdn", "mail"}

def tenant_from_host(host: str, base_domain: str) -> str:
    h = host.split(":")[0].removeprefix("www.")
    labels = h.split(".")
    if h == base_domain or len(labels) <= base_domain.count(".") + 1:
        return "sps"                      # apex -> owner tenant
    sub = labels[0]
    return "sps" if sub in RESERVED_SUBDOMAINS else sub
