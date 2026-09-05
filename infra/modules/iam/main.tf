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
    ]
    sa-webhook = [
      "roles/pubsub.publisher",
      "roles/secretmanager.secretAccessor",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
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
    ]
    sa-toolbox = [
      "roles/cloudsql.client",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
    ]
    sa-agent-engine = [
      "roles/aiplatform.user",
      "roles/secretmanager.secretAccessor",
      "roles/datastore.user",
      "roles/pubsub.publisher",
      "roles/cloudsql.client",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
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
