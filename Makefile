.PHONY: setup lint test test-live run-local deploy deploy-services deploy-infra deploy-agent-engine seed replay-webhook evals

setup:
	uv sync
	uv run pre-commit install
	@command -v gcloud >/dev/null 2>&1 && echo "gcloud account: $$(gcloud config get-value account 2>/dev/null)" || echo "WARNING: gcloud not found on PATH"

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict packages
	uv run mypy --strict services
	uv run mypy config

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test: ## brings up postgres for the ledger integration tests (PHASE_02.md §2.2); CI uses a service container instead
	docker compose up -d postgres
	DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev uv run pytest -m "not live"

test-live: ## needs .env populated (GOOGLE_CLOUD_PROJECT, INTAKE_BUCKET at minimum) -- never runs in CI
	uv run --env-file .env pytest -m live

run-local: ## Phase 1.4 — today this is just postgres; see docs/DEV.md for what's still commented out
	docker compose up -d postgres
	@echo "postgres: postgresql://app:localdev@localhost:5432/ouroboros" # pragma: allowlist secret

GOOGLE_CLOUD_PROJECT ?= ouroboros-507503
OUROBOROS_REGION ?= us-central1
VPC_CONNECTOR ?= ouroboros-dev-conn
DB_HOST ?= 10.175.0.3
INTAKE_BUCKET ?= ouroboros-507503-intake-dev
ARTIFACTS_BUCKET ?= ouroboros-507503-artifacts-dev
# Phase 8.1/8.6 GIS sign-in Client ID -- empty until created via the Cloud Console (docs/BLOCKERS.md)
GOOGLE_OAUTH_CLIENT_ID ?=
# dashboard-api's own URL -- Cloud Run's project-number URL form is deterministic
# (doesn't require the service to already exist to compute), used as the expected
# `audience` for /internal/* routes' own identity-token check (docs/DECISIONS.md).
SELF_BASE_URL ?= https://dashboard-api-492372502792.us-central1.run.app
# Phase 8.2: web/'s dev server origin, so the browser's CORS preflight succeeds. A
# single value for now (local dev only, no production web origin exists yet) --
# --set-env-vars itself uses commas as its own pair-delimiter, so a *second*,
# comma-separated origin here will need gcloud's `^;^` custom-delimiter syntax
# instead of the plain comma-joined form every other var below already uses.
CORS_ALLOWED_ORIGINS ?= http://localhost:5173

deploy: deploy-services deploy-infra deploy-agent-engine ## usage: make deploy ENV=dev -- mirrors .github/workflows/deploy.yml's three jobs, in the same order (services before infra: an Eventarc trigger's destination and any run.invoker binding on a service both need that service to already exist)

deploy-services: ## builds + gcloud-deploys every Cloud Run service (see .github/workflows/deploy.yml for the canonical, CI-run version of these same commands)
	gcloud builds submit --config=services/toolbox/cloudbuild.yaml --gcs-log-dir=gs://ouroboros-507503-artifacts-dev/cloudbuild-logs/ .
	gcloud run deploy toolbox --region=$(OUROBOROS_REGION) \
		--image=$(OUROBOROS_REGION)-docker.pkg.dev/$(GOOGLE_CLOUD_PROJECT)/ouroboros/toolbox:latest \
		--service-account=sa-toolbox@$(GOOGLE_CLOUD_PROJECT).iam.gserviceaccount.com \
		--set-env-vars=TOOLBOX_DB_HOST=$(DB_HOST),TOOLBOX_DB_PORT=5432,TOOLBOX_DB_NAME=ouroboros,TOOLBOX_DB_USER=app \
		--set-secrets=TOOLBOX_DB_PASSWORD=DB_PASSWORD:latest \
		--no-allow-unauthenticated --vpc-connector=$(VPC_CONNECTOR) \
		--vpc-egress=private-ranges-only --ingress=all --port=5000
	gcloud builds submit --config=services/ingest/cloudbuild.yaml --gcs-log-dir=gs://ouroboros-507503-artifacts-dev/cloudbuild-logs/ .
	gcloud run deploy ingest --region=$(OUROBOROS_REGION) \
		--image=$(OUROBOROS_REGION)-docker.pkg.dev/$(GOOGLE_CLOUD_PROJECT)/ouroboros/ingest:latest \
		--service-account=sa-ingest@$(GOOGLE_CLOUD_PROJECT).iam.gserviceaccount.com \
		--set-env-vars=GOOGLE_CLOUD_PROJECT=$(GOOGLE_CLOUD_PROJECT),OUROBOROS_REGION=$(OUROBOROS_REGION),DB_HOST=$(DB_HOST),DB_PORT=5432,DB_NAME=ouroboros,DB_USER=app,ARTIFACTS_BUCKET=$(ARTIFACTS_BUCKET) \
		--set-secrets=DB_PASSWORD=DB_PASSWORD:latest \
		--no-allow-unauthenticated --vpc-connector=$(VPC_CONNECTOR) \
		--vpc-egress=private-ranges-only --ingress=internal \
		--memory=2Gi --cpu=2 --timeout=600
	gcloud builds submit --config=services/dashboard_api/cloudbuild.yaml --gcs-log-dir=gs://ouroboros-507503-artifacts-dev/cloudbuild-logs/ .
	gcloud run deploy dashboard-api --region=$(OUROBOROS_REGION) \
		--image=$(OUROBOROS_REGION)-docker.pkg.dev/$(GOOGLE_CLOUD_PROJECT)/ouroboros/dashboard-api:latest \
		--service-account=sa-dashboard-api@$(GOOGLE_CLOUD_PROJECT).iam.gserviceaccount.com \
		--set-env-vars=GOOGLE_CLOUD_PROJECT=$(GOOGLE_CLOUD_PROJECT),OUROBOROS_REGION=$(OUROBOROS_REGION),DB_HOST=$(DB_HOST),DB_PORT=5432,DB_NAME=ouroboros,DB_USER=app,INTAKE_BUCKET=$(INTAKE_BUCKET),AGENT_ENGINE_RESOURCE_NAME=$(AGENT_ENGINE_RESOURCE_NAME),AUTO_RUN_AFTER_INGEST=$(AUTO_RUN_AFTER_INGEST),GOOGLE_OAUTH_CLIENT_ID=$(GOOGLE_OAUTH_CLIENT_ID),SELF_BASE_URL=$(SELF_BASE_URL),CORS_ALLOWED_ORIGINS=$(CORS_ALLOWED_ORIGINS) \
		--set-secrets=DB_PASSWORD=DB_PASSWORD:latest \
		--allow-unauthenticated --vpc-connector=$(VPC_CONNECTOR) \
		--vpc-egress=private-ranges-only --memory=1Gi \
		--no-cpu-throttling --min-instances=1
	gcloud builds submit --config=services/toolbox_public/cloudbuild.yaml --gcs-log-dir=gs://ouroboros-507503-artifacts-dev/cloudbuild-logs/ .
	$(eval TOOLBOX_URL := $(shell gcloud run services describe toolbox --region=$(OUROBOROS_REGION) --format='value(status.url)'))
	gcloud run deploy toolbox-public --region=$(OUROBOROS_REGION) \
		--image=$(OUROBOROS_REGION)-docker.pkg.dev/$(GOOGLE_CLOUD_PROJECT)/ouroboros/toolbox-public:latest \
		--service-account=sa-toolbox-public@$(GOOGLE_CLOUD_PROJECT).iam.gserviceaccount.com \
		--set-env-vars=GOOGLE_CLOUD_PROJECT=$(GOOGLE_CLOUD_PROJECT),TOOLBOX_BACKEND_URL=$(TOOLBOX_URL) \
		--allow-unauthenticated
	gcloud builds submit --config=services/webhook_receiver/cloudbuild.yaml --gcs-log-dir=gs://ouroboros-507503-artifacts-dev/cloudbuild-logs/ .
	gcloud run deploy webhook-receiver --region=$(OUROBOROS_REGION) \
		--image=$(OUROBOROS_REGION)-docker.pkg.dev/$(GOOGLE_CLOUD_PROJECT)/ouroboros/webhook-receiver:latest \
		--service-account=sa-webhook@$(GOOGLE_CLOUD_PROJECT).iam.gserviceaccount.com \
		--set-env-vars=GOOGLE_CLOUD_PROJECT=$(GOOGLE_CLOUD_PROJECT) \
		--allow-unauthenticated
	gcloud builds submit --config=services/reverify_worker/cloudbuild.yaml --gcs-log-dir=gs://ouroboros-507503-artifacts-dev/cloudbuild-logs/ .
	gcloud run deploy reverify-worker --region=$(OUROBOROS_REGION) \
		--image=$(OUROBOROS_REGION)-docker.pkg.dev/$(GOOGLE_CLOUD_PROJECT)/ouroboros/reverify-worker:latest \
		--service-account=sa-reverify@$(GOOGLE_CLOUD_PROJECT).iam.gserviceaccount.com \
		--set-env-vars=GOOGLE_CLOUD_PROJECT=$(GOOGLE_CLOUD_PROJECT),OUROBOROS_REGION=$(OUROBOROS_REGION),DB_HOST=$(DB_HOST),DB_PORT=5432,DB_NAME=ouroboros,DB_USER=app \
		--set-secrets=DB_PASSWORD=DB_PASSWORD:latest \
		--no-allow-unauthenticated --vpc-connector=$(VPC_CONNECTOR) \
		--vpc-egress=private-ranges-only

deploy-infra: ## usage: make deploy-infra ENV=dev
	terraform -chdir=infra init
	terraform -chdir=infra apply -var-file=environments/$(ENV).tfvars

deploy-agent-engine: ## needs .env populated (AGENT_ENGINE_RESOURCE_NAME set once an engine exists, else this creates one -- add the printed resource name to .env afterward)
	TOOLBOX_MCP_URL=$$(gcloud run services describe toolbox --region=$(OUROBOROS_REGION) --format='value(status.url)') \
		uv run --env-file .env python -m agents.deploy.deploy

seed: ## loads fixtures/projects/demo.yaml — idempotent, safe to re-run
	docker compose up -d postgres
	DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev uv run python scripts/seed.py

replay-webhook: ## Phase 7.1 — usage: make replay-webhook FIXTURE=monitor_event_1
	uv run --env-file .env python scripts/replay_webhook.py --fixture $(FIXTURE)

evals: ## Phase 9.2 — golden set + Vertex AI Evaluation. Needs docker compose up -d postgres toolbox
## and alembic upgrade head first; real, budgeted Parallel + Gemini spend (a few dollars).
	DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev TOOLBOX_MCP_URL=http://localhost:5001 \
		uv run --env-file .env python evals/run_golden.py
	DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev TOOLBOX_MCP_URL=http://localhost:5001 \
		uv run --with "google-cloud-aiplatform[evaluation]" --env-file .env python evals/run_vertex.py

evals-adk: ## Phase 9.2 — adk eval for every ADK eval set (needs seed_eval_fixtures.py + run_golden.py's seed fns first)
	@for set in claim_triage risk_assessor music_agent brand_agent person_agent location_art_agent fact_agent; do \
		case "$$set" in \
			claim_triage) agent=ClaimTriage ;; \
			risk_assessor) agent=RiskAssessor ;; \
			music_agent) agent=MusicAgent ;; \
			brand_agent) agent=BrandAgent ;; \
			person_agent) agent=PersonAgent ;; \
			location_art_agent) agent=LocationArtAgent ;; \
			fact_agent) agent=FactAgent ;; \
		esac; \
		echo "=== $$set ($$agent) ==="; \
		DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev TOOLBOX_MCP_URL=http://localhost:5001 \
			uv run --with "google-adk[eval]" --env-file .env python -c "\
import asyncio; \
from google.adk.evaluation.agent_evaluator import AgentEvaluator; \
asyncio.run(AgentEvaluator.evaluate(agent_module='agents.ouroboros.agent', eval_dataset_file_path_or_dir='evals/adk/$$set.evalset.json', agent_name='$$agent', num_runs=1))" \
		|| exit 1; \
	done
