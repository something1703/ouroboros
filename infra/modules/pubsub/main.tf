# Phase 3.1 event plumbing (PHASE_03.md §3.1): one topic every ingest run publishes to
# when it finishes extracting claims from an asset, with a dead-letter path so a
# permanently-failing delivery doesn't retry forever or vanish silently.

resource "google_pubsub_topic" "claims_extracted" {
  project = var.project_id
  name    = "claims.extracted"
}

resource "google_pubsub_topic" "claims_extracted_dlq" {
  project = var.project_id
  name    = "claims.extracted.dlq"
}

# Anchor subscription for this phase's own acceptance test ("Pub/Sub message received by
# a test subscriber", PHASE_03.md §3.5) and the attachment point for whichever real
# consumer a later phase adds (Phase 5 re-verify worker, Phase 8 dashboard live
# updates) — nothing else subscribes yet.
resource "google_pubsub_subscription" "claims_extracted_verify" {
  project = var.project_id
  name    = "claims-extracted-verify"
  topic   = google_pubsub_topic.claims_extracted.id

  ack_deadline_seconds = 20

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.claims_extracted_dlq.id
    max_delivery_attempts = 5
  }
}

# So a dead-lettered message isn't just unreachable — lets `make test-live` and anyone
# debugging inspect what actually failed delivery.
resource "google_pubsub_subscription" "claims_extracted_dlq_pull" {
  project = var.project_id
  name    = "claims-extracted-dlq-pull"
  topic   = google_pubsub_topic.claims_extracted_dlq.id

  message_retention_duration = "604800s" # 7 days
}

# dashboard-api is gcloud-deployed in deploy.yml's deploy-services job, which always
# runs before terraform-apply (same ordering constraint as infra/modules/eventarc) — so
# by the time this data source is read, the service (and its real URL, needed for the
# push subscription below) already exists.
data "google_cloud_run_v2_service" "dashboard_api" {
  project  = var.project_id
  location = var.region
  name     = var.dashboard_api_service_name
}

# Phase 5.5 (PHASE_05.md §5.5): auto-starts a CLEAR run after ingest, feature-flagged by
# AUTO_RUN_AFTER_INGEST on dashboard-api's own side (this subscription always delivers;
# the endpoint itself decides whether to act, so the flag can be toggled without
# touching infra). A separate subscription from claims_extracted_verify above, which
# stays reserved as a pull-based anchor for whichever other consumer needs it.
resource "google_pubsub_subscription" "claims_extracted_autorun" {
  project = var.project_id
  name    = "claims-extracted-autorun"
  topic   = google_pubsub_topic.claims_extracted.id

  ack_deadline_seconds = 20

  push_config {
    push_endpoint = "${data.google_cloud_run_v2_service.dashboard_api.uri}/internal/runs/auto"
    oidc_token {
      service_account_email = var.sa_scheduler_email
      audience              = data.google_cloud_run_v2_service.dashboard_api.uri
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.claims_extracted_dlq.id
    max_delivery_attempts = 5
  }
}

resource "google_cloud_run_v2_service_iam_member" "dashboard_api_invoker_pubsub" {
  project  = var.project_id
  location = var.region
  name     = var.dashboard_api_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.sa_scheduler_email}"
}

# Required for the dead_letter_policy above to actually forward undeliverable messages
# (docs.cloud.google.com/pubsub/docs/handling-failures, verified 2026-09-03): the
# Pub/Sub service agent needs publisher on the DLQ topic and subscriber on the source
# subscription — without both, Pub/Sub silently cannot dead-letter anything.
resource "google_project_service_identity" "pubsub" {
  provider = google-beta
  project  = var.project_id
  service  = "pubsub.googleapis.com"
}

resource "google_pubsub_topic_iam_member" "pubsub_agent_publishes_dlq" {
  project = var.project_id
  topic   = google_pubsub_topic.claims_extracted_dlq.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_project_service_identity.pubsub.email}"
}

resource "google_pubsub_subscription_iam_member" "pubsub_agent_subscribes_source" {
  project      = var.project_id
  subscription = google_pubsub_subscription.claims_extracted_verify.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_project_service_identity.pubsub.email}"
}

resource "google_pubsub_subscription_iam_member" "pubsub_agent_subscribes_autorun" {
  project      = var.project_id
  subscription = google_pubsub_subscription.claims_extracted_autorun.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_project_service_identity.pubsub.email}"
}

# Phase 7.1/7.2 (PHASE_07.md §7.1, ARCHITECTURE.md §2.5): webhook_receiver verifies a
# Parallel Monitor/Task webhook's signature, then publishes here; reverify_worker is the
# one real subscriber. Mirrors claims_extracted/claims_extracted_dlq's shape exactly.
resource "google_pubsub_topic" "verification_events" {
  project = var.project_id
  name    = "verification.events"
}

resource "google_pubsub_topic" "verification_events_dlq" {
  project = var.project_id
  name    = "verification.events.dlq"
}

# reverify-worker is gcloud-deployed in deploy.yml's deploy-services job, which always
# runs before terraform-apply (same ordering constraint as dashboard_api above) — so by
# the time this data source is read, the service (and its real URL, needed for the push
# subscription below) already exists.
data "google_cloud_run_v2_service" "reverify_worker" {
  project  = var.project_id
  location = var.region
  name     = var.reverify_worker_service_name
}

resource "google_pubsub_subscription" "verification_events_reverify" {
  project = var.project_id
  name    = "verification-events-reverify"
  topic   = google_pubsub_topic.verification_events.id

  ack_deadline_seconds = 20

  push_config {
    push_endpoint = "${data.google_cloud_run_v2_service.reverify_worker.uri}/pubsub/verification"
    oidc_token {
      service_account_email = var.sa_scheduler_email
      audience              = data.google_cloud_run_v2_service.reverify_worker.uri
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.verification_events_dlq.id
    max_delivery_attempts = 5
  }
}

# So a dead-lettered verification event isn't just unreachable — mirrors
# claims_extracted_dlq_pull's rationale exactly.
resource "google_pubsub_subscription" "verification_events_dlq_pull" {
  project = var.project_id
  name    = "verification-events-dlq-pull"
  topic   = google_pubsub_topic.verification_events_dlq.id

  message_retention_duration = "604800s" # 7 days
}

resource "google_cloud_run_v2_service_iam_member" "reverify_worker_invoker_pubsub" {
  project  = var.project_id
  location = var.region
  name     = var.reverify_worker_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.sa_scheduler_email}"
}

resource "google_pubsub_topic_iam_member" "pubsub_agent_publishes_verification_dlq" {
  project = var.project_id
  topic   = google_pubsub_topic.verification_events_dlq.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_project_service_identity.pubsub.email}"
}

resource "google_pubsub_subscription_iam_member" "pubsub_agent_subscribes_verification_reverify" {
  project      = var.project_id
  subscription = google_pubsub_subscription.verification_events_reverify.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_project_service_identity.pubsub.email}"
}
