# PNBallie v2 — CLAUDE.md

## Project
Office foosball score tracker. Mobile-first single-screen webapp.

## Stack
- **Backend:** FastAPI + SQLModel + SQLite + Alembic, managed with `uv` (never write deps manually)
- **Frontend:** Vue 3 (Composition API) + Tailwind CSS + Vite + TypeScript, managed with `npm`
- **Deploy:** Docker Compose (nginx serves frontend + proxies `/api/` to backend)

## Dev Commands
```bash
make dev-backend      # FastAPI on :8000 (with --reload), runs migrations first
make dev-frontend     # Vite on :5173
make dev              # both
make migrate          # run Alembic migrations only
make docker-up        # docker compose up --build -d
make docker-down      # docker compose down
```

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
- Docker (prod-like): http://localhost

## Phone Testing
Mac IP: `192.168.1.120`
- Docker: http://192.168.1.120
- Dev: `npm run dev -- --host` then http://192.168.1.120:5173

## Key Rules
- Never manually edit `pyproject.toml` deps — use `uv add`
- Never manually edit `package.json` deps — use `npm install`
- No vue-router, no Pinia — composables only
- Backend runs from `backend/` dir with `uv run`

## Architecture
- No router: single-screen app
- Composables: `useApi`, `usePlayers`, `useMatch`
- SVG table in `FoosballTable.vue` — inline, scales on any screen
- DB: `match` table (scores, played_at) + `match_player` table (match_id, player_id, side, position)
- Frontend positions: `orange_front`, `orange_back`, `blue_front`, `blue_back` — mapped to side/position on submit
- Validation: scores 0–10, ≥1 player per team, no duplicate players

## Status
- [x] Backend scaffolded + API working
- [x] Frontend scaffolded + builds clean
- [x] Docker + nginx + Makefile
- [ ] Tested on phone
- [ ] Any polish / tweaks needed
