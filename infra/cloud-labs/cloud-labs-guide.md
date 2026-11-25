# Cloud comparison labs

The AWS Terraform baseline remains the main deployment path. The GCP and Azure examples deploy only the stateless Go telemetry service so cloud-specific learning stays separate from the product's source of truth. These are educational deployment starting points, not production environments. They create billable resources; deploy only in a disposable learning project/resource group and delete them when finished.

## AWS: EC2, EKS, and private Route 53

`aws-services/` is an isolated Terraform root for the three services that are not part of the main ECS baseline. Its EC2 instance, EKS cluster/node group, and private hosted zone each have a separate false-by-default enable flag. The EC2 example has no public IP and requires IMDSv2; the EKS control-plane endpoint is private and requires a VPC-reachable administration host. EKS and the hosted zone have ongoing charges while active. Follow the dedicated [AWS services lab guide](aws-services/README.md), use existing private network resources, and destroy the lab after practice. No AWS resources have been applied from this repository.

## Google Cloud: Artifact Registry and Cloud Run

`gcp/cloudbuild.yaml` builds the Go telemetry image, pushes it to Artifact Registry, then deploys a private Cloud Run service with a runtime service account and a two-instance maximum. Create the repository and service account, enable Cloud Build/Run/Artifact Registry APIs, grant narrowly scoped build/deploy permissions, and configure a Cloud Build trigger for this file. For an initial manual run, submit the repository root with `gcloud builds submit --config=infra/cloud-labs/gcp/cloudbuild.yaml .` after configuring the substitutions and IAM. Protect the service with IAM; it is not public by default.

### Google Kubernetes Engine and Secret Manager

`gcp/gke-secrets/` is a separate Terraform root for an opt-in Autopilot cluster, GKE's managed Secret Manager CSI add-on, and an IAM grant for exactly one Kubernetes service account to read one secret. Autopilot provides Workload Identity Federation; the CSI mount reads the secret without copying it into a Kubernetes Secret. The Terraform root deliberately creates no secret version and stores no secret payload. Follow its README to add a synthetic value out of band, mount it through the sample pod, verify the file without printing it, and clean up. The cluster is billable and disabled by default. See Google's official [GKE Secret Manager add-on guide](https://docs.cloud.google.com/secret-manager/docs/secret-manager-managed-csi-component) and [Workload Identity Federation guidance](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/workload-identity).

Cloud Run can autoscale to zero; GKE requires a separately priced cluster. Delete the cluster and Artifact Registry repository after practice.

## Azure: Container Registry and Container Apps

Build and push the image into an Azure Container Registry with `az acr build`, then pass its pinned image reference as `image` to `azure/main.bicep`. The template creates a Log Analytics workspace, Container Apps environment, and a small autoscaling Container App with a health probe and system-assigned identity. Before using a private registry, grant the app identity `AcrPull` on that registry. For secret practice, create a Key Vault secret separately and grant the app identity the Key Vault Secrets User role; do not put secret values in Bicep parameters or source control. The telemetry service needs no secret to run.

The current Azure lab demonstrates Container Apps, managed identity, logs and health probes. Azure Database for PostgreSQL, Service Bus, Application Insights, production networking, and full stack deployment remain future exercises. Delete the resource group after use.

These examples follow the providers' official [Cloud Build to Cloud Run](https://docs.cloud.google.com/build/docs/deploying-builds/deploy-cloud-run), [Container Apps Bicep](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/containerapps), and [Container Apps Key Vault secret](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets) guidance. Commands and templates still require provider-side validation in a disposable account before use.
