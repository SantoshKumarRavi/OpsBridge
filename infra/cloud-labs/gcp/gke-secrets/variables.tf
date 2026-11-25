variable "project_id" {
  type        = string
  description = "Existing disposable GCP project ID. No project is created by this lab."
}

variable "project_number" {
  type        = string
  description = "Numeric project number for the GKE Workload Identity principal."
  validation {
    condition     = can(regex("^[0-9]+$", var.project_number))
    error_message = "project_number must contain only digits."
  }
}

variable "region" {
  type        = string
  default     = "asia-south1"
  description = "Region for the optional GKE Autopilot cluster."
}

variable "enable_gke_lab" {
  type        = bool
  default     = false
  description = "Create billable Autopilot GKE and Secret Manager resources only when explicitly enabled."
}

variable "cluster_name" {
  type    = string
  default = "opsbridge-learning"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,38}[a-z0-9]$", var.cluster_name))
    error_message = "cluster_name must be a lowercase GKE name of 2-40 characters."
  }
}

variable "secret_id" {
  type    = string
  default = "opsbridge-demo-runtime"
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,255}$", var.secret_id))
    error_message = "secret_id must use only letters, digits, underscores, and hyphens."
  }
}

variable "namespace" {
  type    = string
  default = "default"
}

variable "kubernetes_service_account" {
  type    = string
  default = "opsbridge-secret-reader"
}
