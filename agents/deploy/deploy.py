"""Deploy `agents.ouroboros.agent.root_agent` to Vertex AI Agent Engine
(PHASE_05.md §5.5). Idempotent: updates the existing engine if
`AGENT_ENGINE_RESOURCE_NAME` is set (in `.env` or the environment), else creates one
and prints the resource name to add there.

Run: `uv run --env-file .env python -m agents.deploy.deploy` — but note `.env` is a
*local-dev* file (`TOOLBOX_MCP_URL=http://localhost:5001`, `DB_HOST=localhost`,
`PUBLIC_BASE_URL=http://localhost:8080`) used only so this script can import and
construct `root_agent` against a reachable Toolbox locally. Those three values would be
actively wrong baked into the *deployed* engine — found live: an earlier draft of this
script copied `TOOLBOX_MCP_URL`/`DB_HOST`/`PUBLIC_BASE_URL` straight from `os.environ`,
which would have shipped `localhost` URLs no Vertex AI-hosted process can reach (and a
non-HTTPS `PUBLIC_BASE_URL`, which every Monitor-creation call already rejects with a
422 in local testing for exactly this reason). Resolved explicitly below instead,
mirroring how `.github/workflows/deploy.yml` hardcodes `DB_HOST` for Cloud Run rather
than reading it from a local file.

No secret values are passed as `env_vars` here — `sa-agent-engine` already has
`roles/secretmanager.secretAccessor` (infra/modules/iam), and
`packages/common/secrets.get_secret` falls back to Secret Manager whenever the env var
of the same name isn't set, exactly like every other deployed service in this repo.
"""

from __future__ import annotations

import os
import subprocess

import vertexai
from vertexai import agent_engines

from agents.ouroboros.agent import root_agent

# Cloud SQL private IP via the Serverless VPC Access connector — same value
# .github/workflows/deploy.yml hardcodes for every other Cloud Run service; there is no
# Terraform output wired up for this yet (see infra/README.md), so it's repeated here
# rather than shelled out to `gcloud sql instances describe` for one static value.
_PROD_DB_HOST = "10.175.0.3"

# Every version pinned exactly to what's installed locally (`uv pip list --format=freeze`),
# not just left as loose `>=` bounds — found live: Agent Engine's actual `create()` failed
# with a vague, logless `500 InternalServerError` (grpc code 13) the very first time this
# had loose bounds. Per Google's own agent-deployment troubleshooting guide, this class of
# error is commonly a version mismatch between the environment that pickled the agent
# (this one) and whatever the deployed container resolves at build time — `cloudpickle`
# itself already gets auto-pinned by `agent_engines.create()`, but nothing else does
# unless it's pinned here too.
#
# The list itself is every third-party top-level package actually reachable by importing
# `agents.ouroboros.agent` (traced live via `sys.modules` diffing + `importlib.metadata.
# packages_distributions()`, not guessed or copied wholesale from pyproject.toml's full
# dependency list) — found live: a first version missing `openai`/`google-cloud-
# modelarmor`/`google-cloud-pubsub`/`google-cloud-bigquery`/`fastapi` (all real transitive
# imports — e.g. `packages/parallel_client/responses.py` imports `openai` directly, and
# `packages/parallel_client/client.py` screens every response through Model Armor) failed
# at container *startup* with `ModuleNotFoundError`, one package per failed deploy cycle
# until traced properly.
_REQUIREMENTS = [
    "google-adk==2.8.0",
    "google-cloud-aiplatform[agent_engines,adk]==2.1.0",
    "google-genai==2.22.0",
    "parallel-web==1.3.3",
    "sqlalchemy==2.0.52",
    "psycopg[binary]==3.3.5",
    "pydantic==2.13.5",
    "google-cloud-secret-manager==2.30.0",
    "google-cloud-firestore==2.29.0",
    "google-cloud-pubsub==2.39.2",
    "google-cloud-bigquery==3.44.0",
    "google-cloud-modelarmor==0.7.1",
    "google-cloud-discoveryengine==0.20.3",
    "toolbox-core==1.4.0",
    "httpx==0.28.1",
    "structlog==26.1.0",
    "opentelemetry-api==1.42.1",
    "opentelemetry-sdk==1.42.1",
    "opentelemetry-exporter-gcp-trace==1.15.0",
    "PyYAML==6.0.3",
    "python-ulid==4.0.1",
    "openai==3.7.0",
    "fastapi==0.141.1",
]

# Environment-agnostic config: this repo has no separate staging/prod split, so these
# already hold the right deployed value in `.env`. GOOGLE_CLOUD_PROJECT is deliberately
# excluded — found live, Agent Engine reserves that name and auto-injects it itself
# (`400 Environment variable name 'GOOGLE_CLOUD_PROJECT' is reserved`). GOOGLE_CLOUD_
# LOCATION is *not* reserved (only PROJECT was ever named in that error) and must stay
# here: found live, without it the deployed engine's own Gemini calls default to
# resolving models against its us-central1 *deploy* region (`agents/deploy/deploy.py`'s
# `location=region` above, #053) instead of the "global" location this project's models
# actually live in, and fail with a real, distinct 404 (`Publisher model ... was not
# found`) -- the deploy region and the region an agent's own LLM calls resolve against
# are two separate settings, easy to conflate since both are called "location".
_PASSTHROUGH_ENV_VARS = (
    "GOOGLE_CLOUD_LOCATION",
    "GOOGLE_GENAI_USE_ENTERPRISE",
    "PARALLEL_MCP_URL",
    "PARALLEL_GROUNDING_MODE",
    "PARALLEL_PROJECT_BUDGET_USD",
    "FIRESTORE_DATABASE",
    "DB_NAME",
    "DB_USER",
    "OUROBOROS_ENV",
    "LOG_LEVEL",
)


def _run_url(service: str, *, region: str) -> str:
    result = subprocess.run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            service,
            "--region",
            region,
            "--format=value(status.url)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.environ.get("OUROBOROS_REGION", "us-central1")
    # Deliberately *not* GOOGLE_CLOUD_LOCATION (which is "global" in .env, correct for
    # this project's direct Gemini calls elsewhere) -- found live: Agent Engine's
    # create()/update() reject "global" outright, only a real region works. Reuses
    # OUROBOROS_REGION rather than introducing a separate var, since every other
    # regional resource in this repo already uses that name for the same region.
    location = region
    staging_bucket = os.environ.get("ARTIFACTS_BUCKET", f"{project}-artifacts-dev")
    vertexai.init(project=project, location=location, staging_bucket=f"gs://{staging_bucket}")

    app = agent_engines.AdkApp(agent=root_agent, app_name="ouroboros", enable_tracing=True)
    # cloudpickle references our own modules (agents.ouroboros.*, packages.*, config.*)
    # by import path, not by value -- found live: without these, the deployed container
    # fails at startup with "ModuleNotFoundError: No module named 'agents'" the moment it
    # tries to unpickle root_agent, since requirements.txt only carries third-party
    # PyPI packages. Matches pyproject.toml's own [tool.hatch.build.targets.wheel]
    # `packages` list, minus `services` (the FastAPI microservices aren't needed here).
    extra_packages = ["agents", "packages", "config"]
    env_vars = {name: os.environ[name] for name in _PASSTHROUGH_ENV_VARS if os.environ.get(name)}
    env_vars["DB_HOST"] = _PROD_DB_HOST
    env_vars["TOOLBOX_MCP_URL"] = _run_url("toolbox", region=region)
    # Phase 7.1: Monitor webhooks (Reporter's own creation calls) need to reach
    # `webhook-receiver`, the service that actually has a `/webhooks/parallel/*` route
    # -- found live (docs/DECISIONS.md #095) that every Monitor created before this
    # service existed pointed at dashboard-api instead, which 404s; the coil-tightening
    # job (PHASE_07.md §7.3) reconciles those older Monitors' webhook URLs separately.
    env_vars["PUBLIC_BASE_URL"] = _run_url("webhook-receiver", region=region)
    # NOT setting GOOGLE_CLOUD_PROJECT here (docs/DECISIONS.md #069) -- found live,
    # Vertex AI rejects it outright: "Environment variable name 'GOOGLE_CLOUD_PROJECT'
    # is reserved." The platform already injects it for every deployed agent; a
    # one-off `404 database (default) does not exist` from `packages/ledger/
    # projections.py::get_client()`'s Firestore client on a fresh cold start was
    # something else (not investigated further -- didn't recur on retry).
    service_account = f"sa-agent-engine@{project}.iam.gserviceaccount.com"

    # Found live (docs/DECISIONS.md #068): the default resource envelope isn't enough
    # once a real request arrives -- cold start spins up ~11 uvicorn workers at once,
    # and the *one* actually handling the request (loading the Firestore/Toolbox
    # clients, session state, etc.) gets silently SIGKILLed a few seconds in while its
    # idle siblings keep running, the classic signature of an OOM kill (no Python
    # traceback, since nothing catches a SIGKILL). Reproduced on 3/3 consecutive fresh
    # triggers. Worse, `services/dashboard_api/runs.py`'s `stream_query` loop doesn't
    # raise when the server-side stream simply ends (rather than erroring), so the run
    # was silently marked "done" in Firestore despite doing zero work.
    resource_limits = {"cpu": "4", "memory": "8Gi"}

    existing = os.environ.get("AGENT_ENGINE_RESOURCE_NAME")
    if existing:
        engine = agent_engines.get(existing)
        engine.update(
            agent_engine=app,  # type: ignore[arg-type]  # AdkApp genuinely implements StreamQueryable at runtime (verified via issubclass); the installed stub's union just doesn't say so.
            requirements=_REQUIREMENTS,
            extra_packages=extra_packages,
            env_vars=env_vars,
            service_account=service_account,
            resource_limits=resource_limits,
        )
        print(f"Updated Agent Engine: {engine.resource_name}")
        return

    engine = agent_engines.create(
        agent_engine=app,  # type: ignore[arg-type]  # see the matching ignore in update() above
        requirements=_REQUIREMENTS,
        extra_packages=extra_packages,
        display_name="ouroboros-clear",
        description="Ouroboros CLEAR: legal-claims triage, verification, and risk assessment.",
        env_vars=env_vars,
        service_account=service_account,
        min_instances=0,
        max_instances=2,
        resource_limits=resource_limits,
    )
    print(f"Created Agent Engine: {engine.resource_name}")
    print("Add this to .env / Secret Manager as AGENT_ENGINE_RESOURCE_NAME.")


if __name__ == "__main__":
    main()
