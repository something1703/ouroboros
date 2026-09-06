# Vertex AI Search (Discovery Engine) datastore for AskOuroboros's private corpus
# (PHASE_08.md §8.4 / ADK_AGENTS.md §4). Unstructured documents (past clearance memos,
# studio guidelines) ingested from GCS via `scripts/ingest_private_corpus.py` after
# apply -- Terraform creates the empty datastore + search app, not the documents in it.

resource "google_discovery_engine_data_store" "private_corpus" {
  provider      = google-beta
  project       = var.project_id
  location      = "global" # Vertex AI Search search apps require "global" or "eu"/"us" multi-region, not a GCP region like us-central1
  data_store_id = "ouroboros-private-corpus"
  display_name  = "Ouroboros Private Corpus"

  industry_vertical = "GENERIC"
  content_config    = "CONTENT_REQUIRED"
  solution_types    = ["SOLUTION_TYPE_SEARCH"]

  # The API populates document_processing_config with a default digital-parsing
  # config we never declared here -- found live, an un-ignored plan wanted to
  # destroy+recreate the whole datastore just to "remove" a block Terraform never
  # set in the first place. Never let a real `apply` do that once documents exist.
  lifecycle {
    ignore_changes = [document_processing_config]
  }
}

resource "google_discovery_engine_search_engine" "private_corpus" {
  provider      = google-beta
  project       = var.project_id
  engine_id     = "ouroboros-private-corpus-engine"
  collection_id = "default_collection"
  location      = google_discovery_engine_data_store.private_corpus.location
  display_name  = "Ouroboros Private Corpus Search"

  data_store_ids = [google_discovery_engine_data_store.private_corpus.data_store_id]

  common_config {
    company_name = "Ouroboros"
  }

  search_engine_config {
    search_tier    = "SEARCH_TIER_STANDARD"
    search_add_ons = ["SEARCH_ADD_ON_LLM"]
  }
}
