resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = "ouroboros-${var.env}"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  project       = var.project_id
  name          = "ouroboros-${var.env}-${var.region}"
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = var.subnet_cidr
}

# Private Services Access — required for Cloud SQL private IP (Phase 2).
resource "google_compute_global_address" "private_service_range" {
  project       = var.project_id
  name          = "ouroboros-${var.env}-psa-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_service_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_range.name]
}

# Serverless VPC Access connector — lets Cloud Run reach Cloud SQL's private IP.
# Smallest supported footprint (2 e2-micro instances) to keep idle cost minimal.
resource "google_vpc_access_connector" "connector" {
  project       = var.project_id
  name          = "ouroboros-${substr(var.env, 0, 4)}-conn"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = var.connector_cidr
  machine_type  = "e2-micro"
  min_instances = 2
  max_instances = 3
  depends_on    = [google_service_networking_connection.private_service_connection]
}

# Allow internal traffic within the VPC (Cloud Run <-> Toolbox <-> Cloud SQL connector range).
resource "google_compute_firewall" "allow_internal" {
  project = var.project_id
  name    = "ouroboros-${var.env}-allow-internal"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr, var.connector_cidr]
}
