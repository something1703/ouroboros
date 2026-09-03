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

test:
	uv run pytest -m "not live"

test-live:
	uv run pytest -m live

run-local: ## Phase 1.4 — today this is just postgres; see docs/DEV.md for what's still commented out
	docker compose up -d postgres
	@echo "postgres: postgresql://app:localdev@localhost:5432/ouroboros" # pragma: allowlist secret

deploy: ## Phase 1.5 — usage: make deploy ENV=dev
	@echo "TODO (Phase 1.5): terraform -chdir=infra apply -var-file=environments/$(ENV).tfvars, then cloud run + agent engine deploy"

seed: ## Phase 2.2
	@echo "TODO (Phase 2.2): uv run python scripts/seed.py --project demo"

replay-webhook: ## Phase 7.1 — usage: make replay-webhook FIXTURE=monitor_event_1
	@echo "TODO (Phase 7.1): uv run python scripts/replay_webhook.py --fixture $(FIXTURE)"

evals: ## Phase 9.2
	@echo "TODO (Phase 9.2): uv run python evals/run_golden.py && uv run python evals/run_vertex.py"
