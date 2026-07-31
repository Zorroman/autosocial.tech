.PHONY: bootstrap setup dev dev-stop up down docker-up docker-down docker-logs \
        health test lint e2e migrate seed seed-demo clean help

help:
	@echo "make bootstrap   - venv, deps, .env, migrations, admin + demo channel/projects seed"
	@echo "make dev         - start local dev stack (mock providers, isolated SQLite, no Redis needed)"
	@echo "make dev-stop    - stop the local dev stack"
	@echo "make up          - run the full stack (backend, worker, postgres, redis, caddy) via Docker Compose"
	@echo "make down        - stop the Docker Compose stack (add -v manually to also drop volumes)"
	@echo "make health      - curl the backend's bare /health endpoint"
	@echo "make test        - run the pytest suite (mocked providers, no network/cost)"
	@echo "make lint        - run ruff (unused imports/vars, undefined names)"
	@echo "make e2e         - install + run the real Playwright suite against a running stack"
	@echo "make migrate     - run DB migrations against the configured DATABASE_URL"
	@echo "make seed        - seed the local admin user"
	@echo "make seed-demo   - seed a demo channel + short/long/processing/failed projects"
	@echo "make clean       - remove local __pycache__ / .pyc (not volumes -- see 'down')"

bootstrap:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	@[ -f .env ] || cp .env.example .env
	.venv/bin/python migrations.py
	.venv/bin/python seed_admin.py
	.venv/bin/python seed_channel.py
	.venv/bin/python scripts/seed_demo_data.py
	@echo "Bootstrap done. Fill in real API keys in .env if you need them, then: make dev"

setup: bootstrap

dev:
	./scripts/dev-start.sh

dev-stop:
	./scripts/dev-start.sh --stop

up:
	docker compose up -d --build

down:
	docker compose down

docker-up: up
docker-down: down

docker-logs:
	docker compose logs -f backend

health:
	curl -f http://localhost:5000/health

test:
	USE_MOCK_PROVIDERS=true SYNC_JOBS=true .venv/bin/python -m pytest tests/ -q

lint:
	.venv/bin/python -m ruff check .

e2e:
	cd tests/e2e && npm ci && npx playwright install --with-deps chromium && npm run test:e2e

migrate:
	.venv/bin/python migrations.py

seed:
	.venv/bin/python seed_admin.py

seed-demo:
	.venv/bin/python seed_channel.py
	.venv/bin/python scripts/seed_demo_data.py

clean:
	find . -name "__pycache__" -not -path "./.venv*" -exec rm -rf {} +
	find . -name "*.pyc" -delete
