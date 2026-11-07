.PHONY: dev backend frontend index ingest test lint build up down logs

backend:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) -j2 backend frontend

index:
	cd backend && uv run python index/build_index.py

ingest:
	cd backend && uv run python scripts/ingest_vector_index.py --reset

test:
	cd backend && uv run pytest -q
	cd frontend && npm run lint

lint:
	cd backend && uv run ruff check .
	cd frontend && npx eslint src

build:
	cd frontend && npm run build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f
