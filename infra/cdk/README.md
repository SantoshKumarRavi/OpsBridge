# AWS CDK labs

The default `OpsBridgeLabStack` contains the focused S3/SQS/SNS/KMS examples. `ServerlessWorkflowStack` is opt-in: set `INCLUDE_SERVERLESS_LAB=true` when running CDK to include it, then target `OpsBridgeServerlessLabStack` explicitly.

The optional stack demonstrates Lambda + Step Functions Express + IAM-authorized API Gateway, an S3/CloudFront static demo with origin access control, an image-scanned immutable ECR repository, and a dormant AWS Glue Python Shell reconciliation job with an S3-hosted script. The Lambda always returns a synthetic `review_required` result. It cannot approve or reject a real person. The Glue job normalizes a synthetic CSV from and to the dedicated script bucket when manually invoked with `--source_uri` and `--target_uri`; it has no schedule and is not run.

This stack creates billable API Gateway, CloudFront, S3, and related resources. ECR retains its repository on stack deletion; delete the repository explicitly if you pushed images and want them removed. Review the CDK diff and cost estimate before deployment, use a disposable account/region, and destroy temporary resources after practice. EC2, EKS and Route 53 are intentionally not provisioned: they have cost, domain, or lifecycle dependencies that make an unattended portfolio stack a poor fit. The existing Kubernetes manifests provide a safer EKS concepts exercise.
