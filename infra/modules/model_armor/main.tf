# Schema verified 2026-09-03 directly against the Terraform provider's raw docs
# (raw.githubusercontent.com/hashicorp/terraform-provider-google/.../model_armor_template.html.markdown)
# rather than guessed.

resource "google_model_armor_template" "ouroboros_default" {
  project     = var.project_id
  location    = var.region
  template_id = "ouroboros-default"

  filter_config {
    # Blocking-capable — packages/safety/model_armor.py hard-blocks on a HIGH-confidence
    # match, per PHASE_03.md §3.4.
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "MEDIUM_AND_ABOVE"
    }

    # Log-only, per PHASE_03.md §3.4 — real scripts/transcripts legitimately contain
    # PII (real people's names, locations); this must never block ingest.
    sdp_settings {
      basic_config {
        filter_enforcement = "ENABLED"
      }
    }

    # Relevant to the web-excerpt screening path (Phase 4+): Parallel search results
    # could surface a malicious link.
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }
  }

  template_metadata {
    multi_language_detection {
      enable_multi_language_detection = true # our own fixtures are English + Hindi
    }
  }
}
