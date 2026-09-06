# PHASE_09.md §9.4: dashboards + alerts. Log-based metrics feed both the dashboard
# widgets and the alert conditions that can't use a Cloud Run/Pub/Sub built-in metric
# directly (spend-vs-cap and monitor-event volume are domain concepts this project's
# own structured logs carry, not something Cloud Monitoring already tracks).

resource "google_monitoring_notification_channel" "email" {
  project      = var.project_id
  type         = "email"
  display_name = "Ouroboros alerts"
  labels = {
    email_address = var.notification_email
  }
}

# --- Log-based metrics --------------------------------------------------------------

resource "google_logging_metric" "webhook_401_count" {
  project = var.project_id
  name    = "webhook_401_count"
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"webhook-receiver\" AND jsonPayload.event=\"webhook_signature_invalid\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "Webhook 401s (invalid signature)"
  }
}

resource "google_logging_metric" "monitor_events_count" {
  project = var.project_id
  name    = "monitor_events_count"
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"reverify-worker\" AND jsonPayload.event=\"monitor_event_received\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "Monitor events received"
  }
}

resource "google_logging_metric" "reverify_latency_ms" {
  project         = var.project_id
  name            = "reverify_latency_ms"
  filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"reverify-worker\" AND jsonPayload.event=\"reverify_complete\""
  value_extractor = "EXTRACT(jsonPayload.latency_ms)"

  label_extractors = {
    risk_level = "EXTRACT(jsonPayload.risk_level)"
  }

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "DISTRIBUTION"
    unit         = "ms"
    display_name = "Re-verification latency (task-completion-event to evidence-written)"
    labels {
      key        = "risk_level"
      value_type = "STRING"
    }
  }

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 32
      growth_factor      = 2
      scale              = 100
    }
  }
}

# --- Alert policies -------------------------------------------------------------------

resource "google_monitoring_alert_policy" "error_rate" {
  project      = var.project_id
  display_name = "Cloud Run error rate > 5% (any service)"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "5xx / total request ratio"
    condition_threshold {
      filter             = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      denominator_filter = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\""
      comparison         = "COMPARISON_GT"
      threshold_value    = 0.05
      duration           = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.service_name"]
      }
      denominator_aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.service_name"]
      }
      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

resource "google_monitoring_alert_policy" "budget_80_percent" {
  project      = var.project_id
  display_name = "Project spend > 80% of budget cap"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "budget_80_percent logged"
    condition_matched_log {
      filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"budget_80_percent\""
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  alert_strategy {
    notification_rate_limit {
      period = "3600s" # at most one email/hour per project even if several claims trip it back-to-back
    }
  }
}

resource "google_monitoring_alert_policy" "webhook_401_spike" {
  project      = var.project_id
  display_name = "Webhook 401 spike"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "> 5 invalid-signature webhooks in 5 minutes"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/webhook_401_count\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

resource "google_monitoring_alert_policy" "dead_letter_messages" {
  project      = var.project_id
  display_name = "Dead-letter messages present"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "undelivered messages on either DLQ pull subscription"
    condition_threshold {
      filter          = "resource.type=\"pubsub_subscription\" AND metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND (resource.labels.subscription_id=\"claims-extracted-dlq-pull\" OR resource.labels.subscription_id=\"verification-events-dlq-pull\")"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MAX"
      }
      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}
