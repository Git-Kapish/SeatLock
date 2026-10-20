.PHONY: up down migrate test test-svc lint fmt typecheck load-test k8s-local clean

# Docker Compose full stack
up:
	docker compose up --build -d

down:
	docker compose down -v

# Database migrations
migrate:
	uv run alembic -c services/auth/alembic.ini upgrade head
	uv run alembic -c services/events/alembic.ini upgrade head
	@if [ -f services/booking/alembic.ini ]; then uv run alembic -c services/booking/alembic.ini upgrade head; fi

# Testing
test:
	uv run pytest libs/common/tests
	uv run pytest services/auth/tests
	uv run pytest services/events/tests
	@if [ -d services/booking/tests ]; then uv run pytest services/booking/tests; fi
	@if [ -d workers/notifier/tests ]; then uv run pytest workers/notifier/tests; fi

test-svc:
	uv run pytest services/$(S)/tests

# Linting & Formatting
lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy libs/common/ticketrush_common
	uv run mypy services/auth/app
	uv run mypy services/events/app
	@if [ -d services/booking/app ]; then uv run mypy services/booking/app; fi
	@if [ -d workers/notifier/app ]; then uv run mypy workers/notifier/app; fi

# Load Testing
load-test:
	k6 run loadtest/k6/flash_sale.js

# Kubernetes Local (kind)
k8s-local:
	kind create cluster --name ticketrush || true
	kubectl apply -k deploy/k8s/overlays/local

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
