.PHONY: setup dev dev-stop test test-cov lint fmt-check docker-up docker-down docker-logs migrate seed clean help

help:
	@echo "make setup       - create venv, install deps, run migrations, seed admin user"
	@echo "make dev         - start local dev stack (mock providers, isolated SQLite, no Redis needed)"
	@echo "make dev-stop    - stop the local dev stack"
	@echo "make test        - run the pytest suite (mocked providers, no network/cost)"
	@echo "make lint        - run ruff (unused imports/vars, undefined names)"
	@echo "make docker-up   - run the full stack (backend, worker, postgres, redis, caddy) via Docker Compose"
	@echo "make docker-down - stop the Docker Compose stack"
	@echo "make docker-logs - tail backend logs from the Docker Compose stack"
	@echo "make migrate     - run DB migrations against the configured DATABASE_URL"
	@echo "make seed        - seed the local admin user"

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	@[ -f .env ] || cp .env.example .env
	.venv/bin/python migrations.py
	.venv/bin/python seed_admin.py
	@echo "Setup done. Fill in API keys in .env, then: make dev"

dev:
	./scripts/dev-start.sh

dev-stop:
	./scripts/dev-start.sh --stop

test:
	USE_MOCK_PROVIDERS=true SYNC_JOBS=true .venv/bin/python -m pytest tests/ -q

lint:
	.venv/bin/python -m ruff check .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend

migrate:
	.venv/bin/python migrations.py

seed:
	.venv/bin/python seed_admin.py

clean:
	find . -name "__pycache__" -not -path "./.venv*" -exec rm -rf {} +
	find . -name "*.pyc" -delete
