# One service account per runtime, least-privilege project IAM roles.
# See infra/README.md for the human-readable table this generates.

locals {
  sa_roles = {
    sa-ingest = [
      "roles/storage.objectViewer",
      "roles/aiplatform.user",
      "roles/secretmanager.secretAccessor",
      "roles/pubsub.publisher",
      "roles/datastore.user",
      "roles/cloudsql.client",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
      "roles/modelarmor.user",
      "roles/eventarc.eventReceiver",
      # PHASE_06.md §6.4: uploads the low-res proxy MP4 + poster frame it generates to
      # the artifacts bucket (packages/gemini_client/video.py::_generate_proxy_and_poster).
      # Also the fix for a pre-existing, never-yet-exercised gap: the multi-chunk video
      # path (_split_chunks) already uploads chunks back to the intake bucket the same
      # way, which objectViewer alone could never have permitted either.
      "roles/storage.objectCreator",
    ]
    sa-webhook = [
      "roles/pubsub.publisher",
      "roles/secretmanager.secretAccessor",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
      # PHASE_07.md §7.1: dedupes by writing a `webhook_dedupe/{webhook_id}` Firestore
      # doc directly (not via Toolbox — this service has no ledger/Cloud SQL need at
      # all, just Firestore for the dedup check).
      "roles/datastore.user",
    ]
    sa-reverify = [
      "roles/aiplatform.user",
      "roles/secretmanager.secretAccessor",
      "roles/datastore.user",
      "roles/pubsub.publisher",
      "roles/pubsub.subscriber",
      "roles/cloudsql.client",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
    ]
    sa-dashboard-api = [
      "roles/datastore.user",
      "roles/secretmanager.secretAccessor",
      "roles/aiplatform.user",
      "roles/cloudsql.client",
      "roles/bigquery.dataEditor",
      "roles/bigquery.jobUser",
      "roles/pubsub.publisher",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
      # A signed upload URL is only valid for what the signing identity can itself do
      # (PHASE_03.md §3.6) — needed for the actual `PUT` the client performs against it,
      # separate from roles/iam.serviceAccountTokenCreator below (which lets it *sign*).
      "roles/storage.objectCreator",
      # Same principle, the read side (PHASE_06.md §6.4): a signed GET URL for the
      # proxy MP4/poster JPEG is only valid for what sa-dashboard-api can itself read,
      # regardless of the URL's own cryptographic validity — GCS still checks the
      # signing identity's own permissions on the object at request time.
      "roles/storage.objectViewer",
    ]
    sa-toolbox = [
      "roles/cloudsql.client",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
      # Found live deploying Phase 5's toolbox service: DB_PASSWORD is injected via
      # --set-secrets, which Cloud Run itself must read on the revision's behalf.
      "roles/secretmanager.secretAccessor",
    ]
    sa-toolbox-public = [
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
      # Reads PARALLEL_MCP_TOKEN to check the inbound bearer token, and mints its own
      # ID token (via IAM Credentials, not a stored key) to call the private toolbox.
      "roles/secretmanager.secretAccessor",
    ]
    sa-agent-engine = [
      "roles/aiplatform.user",
      "roles/secretmanager.secretAccessor",
      "roles/datastore.user",
      "roles/pubsub.publisher",
      "roles/cloudsql.client",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
      # Found live (docs/DECISIONS.md #066): the deployed agent's own safety-sanitization
      # tool calls Model Armor directly, not just sa-ingest's ingestion-time pass — a real
      # 56-claim CLEAR run failed every specialist claim with `403 Permission
      # 'modelarmor.templates.useToSanitizeUserPrompt' denied` until this was added.
      "roles/modelarmor.user",
    ]
    sa-scheduler = [
      "roles/run.invoker",
      "roles/logging.logWriter",
    ]
    # CI/CD via Workload Identity Federation — no JSON keys. `deploy.yml` runs
    # `terraform apply` against the *entire* infra/ config, so this needs
    # read/write on every resource type that config manages, not just
    # build+deploy actions. The first live run hit real 403s (see
    # docs/DECISIONS.md #019) reading/writing IAM policy bindings, the VPC
    # network, the WIF pool itself, Secret Manager, and Firestore — the
    # *.projectIamAdmin/*.Admin roles below fix that precisely, scoped to
    # exactly the resource types infra/ touches (00_REQUIREMENTS_FROM_USER.md
    # §A2 already called out needing Project IAM Admin for whoever runs
    # Terraform). Add the matching admin role here whenever a new Terraform
    # resource type is introduced in a later phase.
    sa-ci-deploy = [
      "roles/resourcemanager.projectIamAdmin",
      "roles/iam.workloadIdentityPoolAdmin",
      "roles/compute.networkAdmin",
      "roles/vpcaccess.admin",
      "roles/secretmanager.admin",
      "roles/datastore.owner",
      "roles/run.admin",
      "roles/artifactregistry.writer",
      "roles/iam.serviceAccountUser",  # actAs — deploy Cloud Run with --service-account=X
      "roles/iam.serviceAccountAdmin", # getIamPolicy/setIamPolicy ON service accounts — needed to manage the WIF binding on sa-ci-deploy itself
      "roles/cloudbuild.builds.editor",
      "roles/aiplatform.user",
      "roles/storage.admin",
      "roles/serviceusage.serviceUsageConsumer",
      # `gcloud builds submit` (every "Build + deploy X" CI step) streams build
      # output from Cloud Build's default logs bucket, which requires the caller
      # to be a project Viewer/Owner or hold `roles/logging.viewer` -- found live
      # (docs/DECISIONS.md #100): every CI `deploy` run since at least Phase 6 was
      # failing at the *first* build step with "This tool can only stream logs if
      # you are Viewer/Owner of the project", even though the underlying Cloud
      # Build itself succeeded -- the missing permission killed the log-streaming
      # poll, which `gcloud` treats as a fatal error, so no service after the
      # first ever got deployed by CI (every real deploy this session was done by
      # hand, bypassing this bug).
      "roles/logging.viewer",
    ]
  }

  sa_role_pairs = merge([
    for sa, roles in local.sa_roles : {
      for role in roles : "${sa}__${replace(role, "/", "_")}" => { sa = sa, role = role }
    }
  ]...)
}

resource "google_service_account" "sa" {
  for_each = local.sa_roles

  project      = var.project_id
  account_id   = each.key
  display_name = "Ouroboros ${each.key}"
}

resource "google_project_iam_member" "bindings" {
  for_each = local.sa_role_pairs

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.sa[each.value.sa].email}"
}

# sa-dashboard-api signs GCS upload URLs (PHASE_03.md §3.6) with no private key on disk —
# generate_signed_url() falls back to the IAM Credentials API's signBlob when given
# service_account_email + access_token (python-storage's _sign_message), which needs
# Service Account Token Creator granted to the SA *on itself* (self-impersonation).
resource "google_service_account_iam_member" "dashboard_api_signs_urls" {
  service_account_id = google_service_account.sa["sa-dashboard-api"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.sa["sa-dashboard-api"].email}"
}

# --- Workload Identity Federation for GitHub Actions (sa-ci), no JSON keys ---

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  # Only this exact repo may assume sa-ci — never a fork or another repo.
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.sa["sa-ci-deploy"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
