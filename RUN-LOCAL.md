# Run SPS locally (backend + frontend, walkable academy)

One machine, two processes, same-origin cookies. **Local only** — not a deployment target.

## Ports
| Process | Port | How |
|---|---|---|
| Postgres 16 + Redis 7 + FastAPI backend | backend on **:8000** | docker-compose |
| MinIO (local S3) | API **:9000**, console **:9001** | docker-compose |
| Next.js 15 frontend | **:3000** | `next dev` |

MinIO is local S3 so the presign→browser-PUT→confirm flow (ID-card upload, receipts)
works locally. Console at `http://localhost:9001` (user/pass `minioadmin`/`minioadmin`).
Dev/prod use real S3 + KMS and are unaffected (the endpoint override env is unset there).

The frontend talks to the backend through a **same-origin proxy**: `next.config.ts` rewrites
`/api/*` → `http://localhost:8000/api/*` (set by `API_URL`). So the browser only ever sees
`localhost:3000` — auth cookies are first-party, no CORS, no cross-port cookie problems.

## One-time setup
```bash
# 1. frontend env (points the proxy at the local backend)
cp frontend/.env.example frontend/.env.local        # API_URL=http://localhost:8000
```

## Run sequence
```bash
# 2. backend + deps (Postgres/Redis/FastAPI). FEATURE_ACADEMY + JWT_ACADEMY_SECRET
#    are set in docker-compose.yml so the academy (A1–A6) routes are live locally.
docker compose up -d                                 # from repo root
docker compose exec backend alembic upgrade head     # migrations (idempotent)

# 3. seed a walkable academy dataset (idempotent, [SAMPLE] data, local-only).
#    Also creates the MinIO bucket if missing, so ID-card upload works.
docker compose exec backend python scripts/seed_local_academy.py

# 4. frontend
cd frontend && npm install && npm run dev            # http://localhost:3000
```

## Log in
| Who | Where | Credentials |
|---|---|---|
| Staff / admin | `http://localhost:3000/login` → lands `/admin/dashboard` | `sandeep@spstechnosoft.com` / `SpsLocal!2026` |
| Student (A3 two-auth) | API works now (`POST /api/academy/auth/login`); **no login page yet** | `student@local.test` / `Student!2026` |

Both cookie paths are verified on localhost: staff sets `access_token`, student sets the
distinct `academy_access_token` (different secret, `kind=academy_student`). Cookies are
`HttpOnly; SameSite=lax`, no `Secure` (`COOKIE_SECURE=false` for http localhost).

## What the seed gives you
- **1 published course** `python` — `[SAMPLE] Python Programming`, real per-course fee ₹55,000.
- **1 cohort** `[SAMPLE] Batch 2026-Q3` with **4 students, one at each status**: applied /
  tested / offered / active (aptitude score, discount, final_fee, and a paid Payment on the
  active one — so every dashboard state renders).
- The **`offered`** student is the login (`student@local.test`) — so you can walk
  offered → pay → active once the pay page exists.

## Notes
- Academy API is live locally only because `FEATURE_ACADEMY=true` is set in
  `docker-compose.yml` (the deployed dev service keeps it OFF).
- The take page `/take/{token}` is the F5 public page, reused as-is for the 60Q academy paper.
- Seed passwords are dev-only; never used anywhere but local Postgres.
- **Local S3:** the app reaches MinIO via `S3_ENDPOINT_URL`; presigned URLs use
  `S3_PUBLIC_ENDPOINT_URL` (the browser-reachable host). Both are set only in
  docker-compose — **unset in dev/prod, which construct the S3 client exactly as before**.

## Running the backend tests locally
`docker compose exec backend python -m pytest -q` — run this against a **clean DB**
(as CI does). The walkable seed populates courses/cohorts/enrollments, and a couple of
clean-slate tests (e.g. the course-seed reproducibility test) do a global delete that
the seeded rows conflict with. To run tests after seeding, reset the academy data first:
```bash
docker compose exec backend python -c "from sqlalchemy import text; from app.db import get_sessionmaker; \
d=get_sessionmaker()(); [d.execute(text('DELETE FROM '+t)) for t in \
('academy.payments','academy.enrollments','academy.cohorts','academy.students','academy.courses')]; \
d.commit(); from app.academy_seed import seed_courses; \
tid=d.execute(text(\"SELECT id FROM shared.tenants WHERE code='SPS001'\")).scalar_one(); \
seed_courses(d.connection(), tid); d.commit()"
```
Then re-run `scripts/seed_local_academy.py` when you want to browser-walk again.
