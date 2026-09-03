resource "google_bigquery_dataset" "ouroboros" {
  project     = var.project_id
  dataset_id  = "ouroboros"
  location    = var.region
  description = "Nightly + streaming mirror of the Cloud SQL ledger, for analytics and the Parallel BigQuery remote-function enrichment path (Phase 7.5)."
}

# Note for anyone writing SQL against cost_events/verification_history: the `at` column
# (kept as-is to match the Postgres column name exactly) is a reserved word in BigQuery
# Standard SQL — quote it with backticks in queries, e.g. SELECT * FROM cost_events
# ORDER BY `at`. Confirmed live when verifying this module (docs/evidence/02-bigquery.md).

resource "google_bigquery_table" "claims" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.ouroboros.dataset_id
  table_id            = "claims"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  schema = jsonencode([
    { name = "claim_id", type = "STRING", mode = "REQUIRED" },
    { name = "project_id", type = "STRING", mode = "REQUIRED" },
    { name = "studio_id", type = "STRING", mode = "REQUIRED" },
    { name = "kind", type = "STRING", mode = "REQUIRED" },
    { name = "category", type = "STRING", mode = "REQUIRED" },
    { name = "entity_text", type = "STRING", mode = "REQUIRED" },
    { name = "normalized_text", type = "STRING", mode = "REQUIRED" },
    { name = "claim_text", type = "STRING", mode = "REQUIRED" },
    { name = "language", type = "STRING", mode = "REQUIRED" },
    { name = "source", type = "JSON", mode = "NULLABLE" },
    { name = "jurisdictions", type = "STRING", mode = "REPEATED" },
    { name = "priority", type = "INTEGER", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "updated_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "evidence" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.ouroboros.dataset_id
  table_id            = "evidence"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  schema = jsonencode([
    { name = "evidence_id", type = "STRING", mode = "REQUIRED" },
    { name = "claim_id", type = "STRING", mode = "REQUIRED" },
    { name = "cycle", type = "INTEGER", mode = "REQUIRED" },
    { name = "method", type = "STRING", mode = "REQUIRED" },
    { name = "parallel_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "previous_interaction_id", type = "STRING", mode = "NULLABLE" },
    { name = "processor", type = "STRING", mode = "NULLABLE" },
    { name = "output", type = "JSON", mode = "NULLABLE" },
    { name = "basis", type = "JSON", mode = "NULLABLE" },
    { name = "overall_confidence", type = "STRING", mode = "REQUIRED" },
    { name = "cost_usd", type = "NUMERIC", mode = "REQUIRED" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "risk_history" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.ouroboros.dataset_id
  table_id            = "risk_history"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "assessed_at"
  }

  schema = jsonencode([
    { name = "id", type = "INTEGER", mode = "NULLABLE" },
    { name = "claim_id", type = "STRING", mode = "REQUIRED" },
    { name = "evidence_id", type = "STRING", mode = "REQUIRED" },
    { name = "level", type = "STRING", mode = "REQUIRED" },
    { name = "score", type = "FLOAT", mode = "REQUIRED" },
    { name = "rationale", type = "STRING", mode = "REQUIRED" },
    { name = "cost_band", type = "STRING", mode = "NULLABLE" },
    { name = "remediation_suggested", type = "BOOLEAN", mode = "REQUIRED" },
    { name = "remediation_kind", type = "STRING", mode = "NULLABLE" },
    { name = "territory_flags", type = "JSON", mode = "NULLABLE" },
    { name = "assessed_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "cost_events" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.ouroboros.dataset_id
  table_id            = "cost_events"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "at"
  }

  schema = jsonencode([
    { name = "id", type = "INTEGER", mode = "NULLABLE" },
    { name = "project_id", type = "STRING", mode = "NULLABLE" },
    { name = "claim_id", type = "STRING", mode = "NULLABLE" },
    { name = "api", type = "STRING", mode = "REQUIRED" },
    { name = "sku", type = "STRING", mode = "NULLABLE" },
    { name = "units", type = "INTEGER", mode = "REQUIRED" },
    { name = "cost_usd", type = "NUMERIC", mode = "REQUIRED" },
    { name = "at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "verification_history" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.ouroboros.dataset_id
  table_id            = "verification_history"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "at"
  }

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "claim_id", type = "STRING", mode = "REQUIRED" },
    { name = "at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "actor", type = "STRING", mode = "REQUIRED" },
    { name = "from_status", type = "STRING", mode = "NULLABLE" },
    { name = "to_status", type = "STRING", mode = "REQUIRED" },
    { name = "note", type = "STRING", mode = "NULLABLE" },
    { name = "ref", type = "JSON", mode = "NULLABLE" },
  ])
}

# Phase 7.5: the Parallel BigQuery remote-function enrichment path reads from this view.
resource "google_bigquery_table" "claims_for_enrichment" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.ouroboros.dataset_id
  table_id            = "claims_for_enrichment"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT claim_id, entity_text, category, jurisdictions
      FROM `${var.project_id}.${google_bigquery_dataset.ouroboros.dataset_id}.claims`
    SQL
  }

  depends_on = [google_bigquery_table.claims]
}
