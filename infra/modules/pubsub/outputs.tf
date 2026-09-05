output "claims_extracted_topic" {
  value = google_pubsub_topic.claims_extracted.name
}

output "claims_extracted_dlq_topic" {
  value = google_pubsub_topic.claims_extracted_dlq.name
}

output "verification_events_topic" {
  value = google_pubsub_topic.verification_events.name
}

output "verification_events_dlq_topic" {
  value = google_pubsub_topic.verification_events_dlq.name
}
