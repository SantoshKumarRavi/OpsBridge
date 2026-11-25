# GKE Autopilot + Secret Manager lab

This separate, opt-in Terraform root demonstrates GKE Autopilot, the managed Secret Manager CSI add-on, and least-privilege Workload Identity Federation for one Kubernetes service account. It does not deploy the OpsBridge product. The cluster and Secret Manager metadata are disabled by default; enabling them may incur ongoing charges. Review current GKE and Secret Manager pricing before enabling the lab.

Terraform creates a secret resource and grants the `opsbridge-secret-reader` Kubernetes identity access to that one secret. It never creates a secret version or puts a secret value in Terraform state. Add a synthetic value out of band in Google Cloud Console after applying. Enable the GKE and Secret Manager APIs in the disposable project before applying.

## Static validation

```sh
terraform init -backend=false
terraform validate
terraform fmt -check -recursive
terraform test -no-color
```

The mocked Terraform tests confirm that the billable resources are disabled by default and that the enabled plan grants secret access only to the named namespace/service-account identity. They make no Google Cloud API calls.

## Optional learning run

1. Use a disposable project and confirm GKE, Secret Manager, and required APIs are enabled.
2. Create `terraform.tfvars` with `project_id`, `project_number`, and `enable_gke_lab = true`. Do not commit this file.
3. Run `terraform plan` and inspect the cluster, IAM principal, and cost implications before applying.
4. Apply the configuration. Add a synthetic value as a new version of the created secret outside Terraform.
5. Render the Kubernetes templates with `envsubst` using `PROJECT_ID`, `SECRET_ID`, `NAMESPACE`, and `KUBERNETES_SERVICE_ACCOUNT`; apply the resulting `SecretProviderClass` and reader Pod.
6. Wait for the Pod to become ready, then run `kubectl exec -n "$NAMESPACE" opsbridge-secret-mount-check -- test -s /var/secrets/runtime-secret`. This checks that the secret was mounted without printing its value.
7. Delete the Pod and class. Keep `enable_gke_lab = true` in the tfvars file while cleaning up. To delete the cluster, first set `deletion_protection = false` in `main.tf`, apply that change to state, then run `terraform destroy` and confirm the plan.

The Terraform state uses a local backend by default. Keep it private and delete it securely after the learning run. Do not use real credentials or personal data in this lab.
