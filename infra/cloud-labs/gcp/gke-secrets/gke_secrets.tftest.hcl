mock_provider "google" {}

variables {
  project_id     = "opsbridge-test-project"
  project_number = "123456789012"
}

run "billable_resources_are_disabled_by_default" {
  command = plan

  assert {
    condition     = length(google_container_cluster.autopilot) == 0
    error_message = "The GKE cluster must remain disabled unless the lab is explicitly enabled."
  }

  assert {
    condition     = length(google_secret_manager_secret.demo) == 0
    error_message = "The Secret Manager resource must remain disabled unless the lab is explicitly enabled."
  }
}

run "enabled_lab_uses_autopilot_and_scoped_secret_access" {
  command = plan

  variables {
    enable_gke_lab = true
  }

  assert {
    condition     = google_container_cluster.autopilot[0].enable_autopilot
    error_message = "The learning cluster must use GKE Autopilot."
  }

  assert {
    condition     = google_container_cluster.autopilot[0].secret_manager_config[0].enabled
    error_message = "The GKE managed Secret Manager add-on must be enabled."
  }

  assert {
    condition     = google_secret_manager_secret_iam_member.gke_reader[0].role == "roles/secretmanager.secretAccessor"
    error_message = "The Kubernetes workload must only receive the secret accessor role."
  }

  assert {
    condition     = google_secret_manager_secret_iam_member.gke_reader[0].member == "principal://iam.googleapis.com/projects/123456789012/locations/global/workloadIdentityPools/opsbridge-test-project.svc.id.goog/subject/ns/default/sa/opsbridge-secret-reader"
    error_message = "Secret access must be scoped to the intended Kubernetes service account."
  }
}
