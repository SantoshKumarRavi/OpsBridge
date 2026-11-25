locals {
  workload_identity_pool      = "${var.project_id}.svc.id.goog"
  workload_identity_principal = "principal://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${local.workload_identity_pool}/subject/ns/${var.namespace}/sa/${var.kubernetes_service_account}"
}

resource "google_container_cluster" "autopilot" {
  count    = var.enable_gke_lab ? 1 : 0
  project  = var.project_id
  name     = var.cluster_name
  location = var.region

  enable_autopilot    = true
  deletion_protection = true

  secret_manager_config {
    enabled = true
  }

  workload_identity_config {
    workload_pool = local.workload_identity_pool
  }
}

resource "google_secret_manager_secret" "demo" {
  count     = var.enable_gke_lab ? 1 : 0
  project   = var.project_id
  secret_id = var.secret_id

  labels = {
    purpose    = "portfolio-learning"
    managed_by = "terraform"
  }

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "gke_reader" {
  count     = var.enable_gke_lab ? 1 : 0
  project   = var.project_id
  secret_id = google_secret_manager_secret.demo[0].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.workload_identity_principal

  depends_on = [google_container_cluster.autopilot]
}
