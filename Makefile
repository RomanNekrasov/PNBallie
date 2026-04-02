.PHONY: dev-backend dev-frontend dev docker-up docker-down migrate

migrate:
	cd backend && uv run alembic upgrade head

dev-backend: migrate
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
