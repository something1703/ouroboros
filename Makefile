.PHONY: setup lint test test-live run-local deploy seed replay-webhook evals

setup:
	uv sync
	uv run pre-commit install
	@command -v gcloud >/dev/null 2>&1 && echo "gcloud account: $$(gcloud config get-value account 2>/dev/null)" || echo "WARNING: gcloud not found on PATH"

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict packages
	uv run mypy config

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test: ## brings up postgres for the ledger integration tests (PHASE_02.md §2.2); CI uses a service container instead
	docker compose up -d postgres
	DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev uv run pytest -m "not live"

test-live:
	uv run pytest -m live

run-local: ## Phase 1.4 — today this is just postgres; see docs/DEV.md for what's still commented out
	docker compose up -d postgres
	@echo "postgres: postgresql://app:localdev@localhost:5432/ouroboros" # pragma: allowlist secret

deploy: ## usage: make deploy ENV=dev
	terraform -chdir=infra init
	terraform -chdir=infra apply -var-file=environments/$(ENV).tfvars
	@echo "TODO (Phase 3+): per-service cloud run deploy; TODO (Phase 5.5): agent engine deploy — no service has application code yet"

seed: ## loads fixtures/projects/demo.yaml — idempotent, safe to re-run
	docker compose up -d postgres
	DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev uv run python scripts/seed.py

replay-webhook: ## Phase 7.1 — usage: make replay-webhook FIXTURE=monitor_event_1
	@echo "TODO (Phase 7.1): uv run python scripts/replay_webhook.py --fixture $(FIXTURE)"

evals: ## Phase 9.2
	@echo "TODO (Phase 9.2): uv run python evals/run_golden.py && uv run python evals/run_vertex.py"
