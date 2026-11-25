output "cluster_name" {
  value       = var.enable_gke_lab ? google_container_cluster.autopilot[0].name : null
  description = "Name of the optional GKE Autopilot cluster."
}

output "secret_resource_name" {
  value       = var.enable_gke_lab ? google_secret_manager_secret.demo[0].name : null
  description = "Secret metadata resource. Terraform deliberately does not create or store a secret value."
}

output "workload_identity_principal" {
  value       = local.workload_identity_principal
  description = "Kubernetes service-account principal granted access to this one secret."
}
