# PHASE_09.md §9.4's dashboard: requests/errors/latency per service, Parallel spend
# signal (budget_80_percent), monitor events per day, re-verification latency.
resource "google_monitoring_dashboard" "ouroboros" {
  project = var.project_id
  dashboard_json = jsonencode({
    displayName = "Ouroboros"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 6, height = 4, xPos = 0, yPos = 0
          widget = {
            title = "Request count per service"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\""
                    aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["resource.labels.service_name"] }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          width = 6, height = 4, xPos = 6, yPos = 0
          widget = {
            title = "5xx error count per service"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
                    aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["resource.labels.service_name"] }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          width = 6, height = 4, xPos = 0, yPos = 4
          widget = {
            title = "Request latency (p95) per service"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_latencies\""
                    aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_PERCENTILE_95", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["resource.labels.service_name"] }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          width = 6, height = 4, xPos = 6, yPos = 4
          widget = {
            title = "Re-verification latency (p50/p95), task-completion-event to evidence-written"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/reverify_latency_ms\""
                    aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_PERCENTILE_95", crossSeriesReducer = "REDUCE_MEAN" }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          width = 4, height = 4, xPos = 0, yPos = 8
          widget = {
            title = "Monitor events / day"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/monitor_events_count\""
                    aggregation = { alignmentPeriod = "86400s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM" }
                  }
                }
                plotType = "STACKED_BAR"
              }]
            }
          }
        },
        {
          width = 4, height = 4, xPos = 4, yPos = 8
          widget = {
            title = "Webhook 401s (invalid signature)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/webhook_401_count\""
                    aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM" }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          width = 4, height = 4, xPos = 8, yPos = 8
          widget = {
            title = "Dead-letter queue depth"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"pubsub_subscription\" AND metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND (resource.labels.subscription_id=\"claims-extracted-dlq-pull\" OR resource.labels.subscription_id=\"verification-events-dlq-pull\")"
                    aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_MAX", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["resource.labels.subscription_id"] }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        }
      ]
    }
  })
}
