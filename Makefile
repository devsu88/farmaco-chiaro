.PHONY: dev backend frontend dataset index eval test lint build check smoke report-logs up down logs

backend:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) -j2 backend frontend

dataset:
	cd backend && uv run python -m aifa_rag.cli dataset

index:
	cd backend && uv run python -m aifa_rag.cli index

eval:
	cd backend && uv run python -m aifa_rag.cli eval

test:
	cd backend && uv run pytest -q
	cd frontend && npm run lint

lint:
	cd backend && uv run ruff check .
	cd frontend && npx eslint src

check: test
	cd backend && uv run ruff check .
	cd frontend && npm run build
	python3 scripts/check_ai_native.py

smoke:
	python3 scripts/smoke.py $(SMOKE_ARGS)

report-logs:
	@test -n "$(LOGS)" || (echo "Uso: make report-logs LOGS=file.jsonl"; exit 1)
	python3 scripts/log_report.py "$(LOGS)" $(REPORT_ARGS)

build:
	cd frontend && npm run build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f
