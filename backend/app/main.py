from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .config import settings
from .context import RequestContext, set_context, tenant_from_host, VERTICAL

app = FastAPI(title="SPS Technosoft API", version="0.1.0")

@app.middleware("http")
async def tenant_context(request: Request, call_next):
    """Resolve tenant (from Host) + business unit (from path) for every request.
    NOTE: in production also verify the JWT and cross-check tenant_id against the
    Host to prevent header spoofing (see TENANCY_AND_ROUTING doc)."""
    host = request.headers.get("host", settings.app_base_domain)
    tenant_slug = tenant_from_host(host, settings.app_base_domain)
    seg = request.url.path.lstrip("/").split("/", 1)[0]
    bu = VERTICAL.get(seg)
    set_context(RequestContext(tenant_id=tenant_slug, business_unit_id=bu))
    return await call_next(request)

@app.get("/healthz")
def healthz():
    # DEPENDENCY-FREE on purpose — this is the ECS/ALB health check. It must
    # NEVER touch RDS/Redis, so a data-tier outage can't crash-loop the service.
    return {"status": "ok", "env": settings.env, "region": settings.aws_region}


@app.get("/readyz")
def readyz():
    # DEEP check for OUR verification only — NOT wired to the ECS health check.
    # Lazily probes DB (SELECT 1) and Redis (PING); 503 if either is down.
    from .db import check_db, check_redis

    report = {"db": "ok", "redis": "ok"}
    healthy = True
    try:
        check_db()
    except Exception as e:  # noqa: BLE001 - report, don't crash
        report["db"] = f"error: {type(e).__name__}"
        healthy = False
    try:
        check_redis()
    except Exception as e:  # noqa: BLE001
        report["redis"] = f"error: {type(e).__name__}"
        healthy = False

    if not healthy:
        return JSONResponse(status_code=503, content={"status": "degraded", **report})
    return {"status": "ready", **report}

@app.get("/api/whoami")
def whoami(request: Request):
    from .context import get_context
    c = get_context()
    return {"tenant": c.tenant_id, "business_unit": c.business_unit_id, "host": request.headers.get("host")}

# Routers (build these out per Master Architecture):
# from .routers import auth, candidates, jobs, client_portal, admin, tenants
# app.include_router(auth.router, prefix="/api/auth")
