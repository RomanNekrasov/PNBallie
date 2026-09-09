# PNBallie v2 — CLAUDE.md

## Project
Office foosball score tracker. Mobile-first webapp with game and statistics views.

PNBallie is a personal project. Follow `K3S_APP_MIGRATION_PLAN.md` and the
current README; provincial development and visual standards do not apply.

## Stack
- **Backend:** FastAPI + SQLModel + SQLite + Alembic, managed with `uv` (never write deps manually)
- **Frontend:** Vue 3 (Composition API) + Tailwind CSS + Vite + TypeScript, managed with `npm`
- **Local containers:** Docker Compose; Nginx serves the frontend on port 8080 and proxies `/api/` to the backend on port 8000.
- **Release/deployment:** private multi-architecture GHCR images; Flux/k3s desired state belongs in `spark-homelab`.
- **Azure:** retained VM, configuration, images and data for rollback; the legacy backend is stopped.

## Dev Commands
```bash
make dev-backend      # FastAPI on :8000 (with --reload), runs migrations first
make dev-frontend     # Vite on :5173
make dev              # both
make migrate          # run Alembic migrations only
make docker-up        # docker compose up --build -d
make docker-down      # docker compose down
make check            # lint, tests, type check and production build
```

Install dependencies and configure runtime authentication as described in
README.md. Native development needs exported `ENTRA_*` variables; Compose
loads `.env` automatically. Frontend configuration is loaded from `/config.json`.

## Migrations (Alembic)
```bash
cd backend
uv run alembic revision --autogenerate -m "description"   # generate migration
uv run alembic upgrade head                                # apply migrations
uv run alembic downgrade -1                                # rollback one step
```
- `render_as_batch=True` is enabled for SQLite compatibility
- `sqlmodel.sql.sqltypes` is auto-imported in the Mako template

## Local Dev URLs
- Frontend (dev): http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Docker (prod-like): http://localhost:8080

## Phone Testing
Use an HTTPS origin registered as an Entra SPA redirect. The homelab runbook
provides the private test URL. Verify phone layouts separately; do not infer
phone acceptance from backend or desktop checks.

## Key Rules
- Never manually edit `pyproject.toml` deps — use `uv add`
- Never manually edit `package.json` deps — use `npm install`
- Vue Router owns `/` and `/stats`; keep shared state in composables, without Pinia.
- Backend runs from `backend/` dir with `uv run`
- Require Entra v2 access tokens; `ENTRA_AUDIENCE` is the API client-ID GUID, while the frontend scope is `api://<API-client-id>/user`.
- Keep credentials, local configuration and database files out of Git and image contexts.
- Do not place Kubernetes resources here or redeploy current images into the frozen Azure stack.

## Architecture
- Router: authenticated game (`/`) and statistics (`/stats`) views.
- Composables: `useApi`, `usePlayers`, `useMatch`, `useStats`
- SVG table in `FoosballTable.vue` — inline, scales on any screen
- DB: `match` table (scores, played_at) + `match_player` table (match_id, player_id, side, position)
- Frontend positions: `orange_front`, `orange_back`, `blue_front`, `blue_back` — mapped to side/position on submit
- Validation: scores 0–10, ≥1 player per team, no duplicate players

## Migration status

The k3s application and tunnel are active with the final Azure data. Full
source comparison passed after replacing the backend pod, and a fresh
encrypted database backup was verified. The retained Azure backend passed a
restart/rollback rehearsal and is stopped again.
Public availability still needs the tunnel's HTTP origin corrected, followed
by public HTTPS, Entra login and authenticated scoring checks. Phase 6 remains
in progress. The current acceptance checklist and evidence live in
`spark-homelab/docs/phase-6-pnballie.md`. Preserve SQLite and the Azure rollback
set; do not mark the migration complete until every acceptance gate is demonstrated.
