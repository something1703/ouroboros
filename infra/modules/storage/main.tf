# Bucket names are prefixed with the project ID for global uniqueness (GCS bucket
# names are global across all of Google Cloud, not just this project) — see
# docs/DECISIONS.md for the naming deviation from the plan's `ouroboros-intake-{env}`.

resource "google_storage_bucket" "intake" {
  project                     = var.project_id
  name                        = "${var.project_id}-intake-${var.env}"
  location                    = var.region
  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }
  # Found live: neither bucket had any CORS policy at all, so every browser-side
  # fetch() against a signed URL -- pdfjs's own PDF load in ScriptView.tsx, not just
  # an <a>/<video> tag, which don't need this -- was unconditionally blocked
  # regardless of whether the underlying object itself was real. A signed URL's
  # query-string auth has nothing to do with CORS; the *bucket* has to say which
  # browser origins may read its objects via fetch/XHR, independent of who signed
  # the URL. GET/HEAD only -- this project's web/ never writes to these buckets
  # directly, only through the dashboard-api's own signed *upload* URLs, which are
  # PUT requests the browser also needs this for.
  cors {
    origin          = var.cors_origins
    method          = ["GET", "HEAD", "PUT"]
    response_header = ["Content-Type", "Content-Length"]
    max_age_seconds = 3600
  }
}

# Vertex AI's own Gemini service agent (not sa-ingest, not whoever calls the API) needs
# read access to a gs:// object before it will fetch it for types.Part.from_uri — found
# live: extract_script_claims failed with a 403 from
# service-<project-number>@gcp-sa-aiplatform.iam.gserviceaccount.com until this was
# granted. See docs/DECISIONS.md.
resource "google_project_service_identity" "vertex_ai" {
  provider = google-beta
  project  = var.project_id
  service  = "aiplatform.googleapis.com"
}

resource "google_storage_bucket_iam_member" "vertex_ai_reads_intake" {
  bucket = google_storage_bucket.intake.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_project_service_identity.vertex_ai.email}"
}

resource "google_storage_bucket" "artifacts" {
  project                     = var.project_id
  name                        = "${var.project_id}-artifacts-${var.env}"
  location                    = var.region
  uniform_bucket_level_access = true
  # Proxies, posters, and exports (PDFs, the clearance CSV) are all read from here
  # via a signed URL fetch/download -- same CORS gap as intake, same fix.
  cors {
    origin          = var.cors_origins
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type", "Content-Length"]
    max_age_seconds = 3600
  }
}

# Shared across envs — large sample fixtures (scripts, cuts) are not env-specific.
resource "google_storage_bucket" "fixtures" {
  project                     = var.project_id
  name                        = "${var.project_id}-fixtures"
  location                    = var.region
  uniform_bucket_level_access = true
}
