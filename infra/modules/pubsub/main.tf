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
