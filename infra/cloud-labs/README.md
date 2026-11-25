# Cloud provider practice environments

AWS Terraform is the deployment baseline. Runnable starting configurations for GCP Cloud Run and Azure Container Apps are in this directory; neither deploys the whole stack a second time. See `cloud-labs-guide.md` before creating billable resources.

The separate `aws-services/` Terraform root covers EC2, EKS, and private Route 53 examples. Every resource group is opt-in and false by default; validate it without credentials, then use a disposable AWS account to plan/apply only after reviewing costs.

- Google Cloud: `gcloud builds submit`, Artifact Registry, Secret Manager, Cloud Run revisions, and Cloud Logging. The separate `gcp/gke-secrets/` Terraform root now configures an opt-in GKE Autopilot cluster, the managed Secret Manager CSI add-on, and secret-scoped Workload Identity access.
- Azure: Container Registry, Container Apps environment, Key Vault role assignment, Log Analytics, and managed identity. The Bicep example deploys only Go telemetry.
- For each lab, deploy only the gateway plus the AI runtime and compliance API. Keep database and secret services in that cloud and use the same OpenAPI/event contract.

These environments create billable resources. Review pricing and destroy lab resources after the learning exercise.
