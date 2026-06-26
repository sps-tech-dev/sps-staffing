from fastapi.testclient import TestClient
from app.main import app

def test_healthz():
    r = TestClient(app).get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"

def test_tenant_resolution_apex():
    r = TestClient(app).get("/api/whoami", headers={"host": "spstechnosoft.com"})
    assert r.json()["tenant"] == "sps"

def test_tenant_resolution_subdomain():
    r = TestClient(app).get("/staffing-and-recruitment", headers={"host": "ampf.spstechnosoft.com"})
    # path has no route, but middleware still resolves context for /api routes
