output "claims_extracted_topic" {
  value = google_pubsub_topic.claims_extracted.name
}

output "claims_extracted_dlq_topic" {
  value = google_pubsub_topic.claims_extracted_dlq.name
}
