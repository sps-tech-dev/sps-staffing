# Backend (FastAPI)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000   # http://localhost:8000/healthz
```
Tenant context is set per-request from the JWT (`tenant_id`) + the vertical path
(`business_unit_id`). Every repository query is scoped by both. See
`docs/architecture/SPS_TECHNOSOFT_MASTER_ARCHITECTURE_V2_TECHNICAL` and `..._TENANCY_AND_ROUTING`.
