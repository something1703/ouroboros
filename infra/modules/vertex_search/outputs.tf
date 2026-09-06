output "data_store_id" {
  value = google_discovery_engine_data_store.private_corpus.data_store_id
}

output "location" {
  value = google_discovery_engine_data_store.private_corpus.location
}

output "engine_id" {
  value = google_discovery_engine_search_engine.private_corpus.engine_id
}
