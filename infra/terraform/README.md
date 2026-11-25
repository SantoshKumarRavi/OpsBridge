# AWS ECS deployment slice

This Terraform root defines an AWS ECS/Fargate deployment slice for ten OpsBridge services: `api-gateway`, `compliance-api`, `ai-runtime`, `integration-service`, `webhook-gateway`, `telemetry-service`, `celery-worker`, `celery-beat`, `realtime-service`, and `event-consumer`. The worker and beat tasks reuse the compliance API image with different commands. Supporting resources include an HTTPS ALB, RDS PostgreSQL, S3, service discovery, CloudWatch logs, ECS CPU scaling, SQS/SNS examples, and deployment rollback.

The HTTPS ALB sends normal API traffic to the gateway and `/ws/*` WebSocket traffic to the realtime service. Celery processes uploaded documents; beat publishes the transactional outbox; the event consumer writes Kafka events to its PostgreSQL projection. Beat and the projection consumer stay at one task by default; they are excluded from generic CPU autoscaling to avoid duplicate schedulers or uncontrolled consumer groups.

This is a more complete workflow deployment template, not a one-command production stack. RabbitMQ, Redis/Valkey, and Kafka remain externally managed dependencies. Supply private endpoints and Secrets Manager ARNs for the RabbitMQ URL, Celery Redis URL, realtime Redis URL, realtime ticket secret, and gateway rate-limit Redis URL; supply a private Kafka bootstrap list reachable from the VPC. Kafka client TLS is the default (`kafka_security_protocol = "ssl"`); both `ssl` and isolated-development `plaintext` are supported. The event consumer reuses the RDS-managed master secret. Full Prometheus/Grafana/Collector deployment, hosted cloud rollout, provider callbacks, and operational evidence remain outside this root. Do not present Terraform configuration or mocked tests as proof of a live deployment.

## Validation

CI runs formatting and provider-backed static validation without AWS credentials or resource creation:

```sh
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform test -no-color
```

The mocked-provider Terraform tests verify public/private subnet boundaries, no public ECS IPs, ALB access restricted to gateway and WebSocket listener ports, Celery worker command and broker-secret wiring, singleton beat scheduling, realtime WebSocket routing, and the event consumer's RDS secret wiring. `terraform test` uses an in-memory mock provider and creates no AWS resources or cloud credentials.

## Deployment outline

1. Build and publish immutable container images for each key in `container_images`; Celery worker and beat use the compliance API image.
2. Provision or select private RabbitMQ, Redis/Valkey, and Kafka endpoints. Create Secrets Manager entries for connection URLs, the realtime ticket key, and internal service credentials. Configure Kafka for TLS or choose plaintext only in an isolated development network.
3. Supply a dedicated state backend and reviewed variable values, including a VPC, at least two public ALB subnets, at least two private ECS/RDS subnets in distinct availability zones, certificate, public API origin, allowed frontend origins, OIDC settings, secret ARNs, Kafka endpoints, and image digests. Private subnets need NAT egress or appropriate VPC endpoints for ECR image pulls, CloudWatch Logs, Secrets Manager, SQS/SNS, and external provider calls. Do not commit credentials or production `.tfvars` files.
4. Run `terraform plan` and review the complete plan, including ongoing AWS costs and the deletion-protected database.
5. Apply only in an explicitly selected AWS account and environment.
6. Verify ECS task health, ALB health checks for API and WebSocket targets, CloudWatch logs, service discovery, queue processing, outbox publication, projection idempotency, database connectivity, scaling, and rollback.

The internet-facing ALB uses public subnets; ECS tasks and PostgreSQL use private subnets, and ECS tasks have no public IP. The ALB security group can reach only API gateway port 8080 and realtime port 8091; service-to-service traffic uses the service security group. Each ECS task has its own task role; only compliance API and Celery worker receive S3 document-bucket permissions, limited to list/get/put. ECS deployment circuit breakers are enabled with rollback. HTTP-facing services have CPU target tracking, with a default maximum of two tasks controlled by `ecs_service_max_capacity`. Celery worker scaling needs queue-depth signals, while beat and the projection consumer stay single-task until their coordination/group strategy is reviewed. These are demonstration settings, not capacity recommendations. Scaling behavior and rollback still need a credentialed deployment exercise to establish runtime evidence.

This repository currently has no configured remote Terraform backend in this root. Do not use a local state file for a shared or production deployment; configure and review remote state, locking, access controls, and recovery first.
