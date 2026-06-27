from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .routers import auth as auth_router
from .routers import me as me_router
from .routers import staffing as staffing_router
from .routers import employee as employee_router
from .routers import admin as admin_router
from .routers import ai as ai_router
from .routers import privacy as privacy_router

app = FastAPI(title="SPS Technosoft API", version="0.1.0")

# Tenant isolation model (see docs/DECISIONS.md): tenant_id comes from the verified
# JWT (authoritative), set per-request by the get_current_context dependency on
# protected routes — NOT from a global Host-parsing middleware. The Host↔session
# cross-check is deferred until real tenant subdomains + CloudFront exist.

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(me_router.router, prefix="/api/me", tags=["me"])
app.include_router(staffing_router.router, prefix="/api", tags=["staffing"])
app.include_router(employee_router.router, prefix="/api/employee", tags=["employee"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["admin"])
app.include_router(ai_router.router, prefix="/api/ai", tags=["ai"])
app.include_router(privacy_router.router, prefix="/api/privacy", tags=["privacy"])


# ── Canonical error envelope (Master Architecture Part 31) ───────
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    d = exc.detail
    err = {"code": d.get("code", "ERROR"), "message": d.get("message", "")} if isinstance(d, dict) \
        else {"code": "ERROR", "message": str(d)}
    return JSONResponse(status_code=exc.status_code, content={"error": err})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Map to a clean, JSON-serializable shape (raw errors() can embed a ValueError).
    details = [
        {"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": "Invalid request", "details": details}},
    )


@app.get("/healthz")
def healthz():
    # DEPENDENCY-FREE on purpose — this is the ECS/ALB health check. It must
    # NEVER touch RDS/Redis, so a data-tier outage can't crash-loop the service.
    return {"status": "ok", "env": settings.env, "region": settings.aws_region}


@app.get("/readyz")
def readyz():
    # DEEP check for OUR verification only — NOT wired to the ECS health check.
    from .db import check_db, check_redis

    report = {"db": "ok", "redis": "ok"}
    healthy = True
    try:
        check_db()
    except Exception as e:  # noqa: BLE001
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
