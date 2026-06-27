# SPS Technosoft — Web (Fresh Next.js Starter)

Runnable foundation (Phase **F0**) for rebuilding the portal front end on a modern,
responsive, future-proof stack. See **SPS_TECHNOSOFT_FRONTEND_BUILD_SPEC** for the
full plan and feature-parity matrix.

## Stack
Next.js 15 (App Router, RSC) · React 19 · TypeScript (strict) · Tailwind CSS v4 ·
TanStack Query · lucide-react · recharts · React Hook Form + Zod · next-intl · @dnd-kit.

## Run
```bash
pnpm install        # or npm install
cp .env.example .env.local   # set API_URL to your FastAPI backend (optional)
pnpm dev            # http://localhost:3000
```
The demo dashboards (`/candidate`, `/employer`) render with **mock data** when no
backend is present, so it runs immediately. Point `API_URL` at FastAPI and the typed
client in `lib/api` will use the real `/api/*` read-models.

## What's included (extend from here)
- **Brand tokens + fonts** — `app/globals.css` (`@theme`), Sora/DM Sans/DM Mono via `next/font`.
- **Responsive AppShell** — `components/shell` (full sidebar → icon-rail → mobile drawer + bottom tab bar).
- **UI kit** — `components/kit` (StatCard, StatusPill, ProgressRing, PipelineDonut, SectionCard, EmptyState, Skeleton, CompanyLogo hexagon) — ported 1:1 from the Angular kit.
- **Typed API client** — `lib/api/client.ts` (cookies, Idempotency-Key, 401 silent-refresh, error envelope).
- **Role middleware** — `middleware.ts` (replaces the four Angular guards).
- **Feature flags** — `lib/feature-flags.ts` (mirrors the backend; off ⇒ hidden + 404).

## Folder map
```
app/(marketing) (auth*) (portal) (admin*)   # route groups — add screens here
components/{ui,kit,shell,widgets}
lib/{api,auth,feature-flags,nav,utils}
middleware.ts · styles/tokens via globals.css
```
`(auth)` and `(admin)` groups are stubbed in the spec — add screens per the migration plan (F1–F6).

## Responsive behaviour
- **mobile (<768px):** sidebar hidden → hamburger drawer + bottom tab bar; cards stack.
- **tablet (768–1024px):** sidebar collapses to an icon rail (hover to expand).
- **laptop/desktop (≥1024px):** full sidebar + topbar; 4-col KPI grids.

## Next steps
F1 Auth + candidate data → F2 employer kanban (@dnd-kit) → F3 employee SLA →
F4 admin tables (TanStack Table) → F5 marketing + i18n (32 locales) → F6 AI widgets + DPDP.
