variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "project_name" {
  type    = string
  default = "opsbridge"
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "At least two public subnets in distinct availability zones for the internet-facing ALB."
  validation {
    condition     = length(var.public_subnet_ids) >= 2
    error_message = "Provide at least two public subnet IDs for the ALB."
  }
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "At least two private subnets in distinct availability zones for ECS tasks and PostgreSQL. Configure NAT or required VPC endpoints for outbound AWS/provider calls."
  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "Provide at least two private subnet IDs for ECS tasks and PostgreSQL."
  }
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for the HTTPS application load balancer."
}

variable "internal_service_token_secret_arn" {
  type        = string
  description = "Secrets Manager ARN containing the gateway-to-service shared token."
  sensitive   = true
}

variable "rate_limit_redis_url_secret_arn" {
  type        = string
  description = "Secrets Manager ARN containing a private Redis/Valkey connection URL for the shared gateway rate limiter."
  sensitive   = true
}

variable "rabbitmq_url_secret_arn" {
  type        = string
  description = "Secrets Manager secret containing the private RabbitMQ AMQP URL used by Django and Celery."
  sensitive   = true
}

variable "celery_redis_url_secret_arn" {
  type        = string
  description = "Secrets Manager secret containing the private Redis URL for Celery results and task state."
  sensitive   = true
}

variable "realtime_redis_url_secret_arn" {
  type        = string
  description = "Secrets Manager secret containing the private Redis URL used by the realtime service."
  sensitive   = true
}

variable "realtime_ticket_secret_arn" {
  type        = string
  description = "Secrets Manager secret containing the shared REALTIME_TICKET_SECRET for gateway and realtime service."
  sensitive   = true
}

variable "kafka_bootstrap_servers" {
  type        = string
  description = "Private Kafka bootstrap endpoints reachable from the ECS tasks; Kafka cluster provisioning is external to this Terraform root."
  validation {
    condition     = length(trimspace(var.kafka_bootstrap_servers)) > 0
    error_message = "Provide private Kafka bootstrap endpoints for the outbox publisher and event consumer."
  }
}

variable "kafka_security_protocol" {
  type        = string
  default     = "ssl"
  description = "Kafka client transport protocol. Use ssl for encrypted broker connections; plaintext is for isolated development only."
  validation {
    condition     = contains(["ssl", "plaintext"], var.kafka_security_protocol)
    error_message = "kafka_security_protocol must be ssl or plaintext."
  }
}

variable "public_api_origin" {
  type        = string
  description = "Public HTTPS origin for the API gateway and realtime WebSocket endpoint, without a trailing slash."
  validation {
    condition     = can(regex("^https://[^/]+$", var.public_api_origin))
    error_message = "public_api_origin must be an https:// origin with no path or trailing slash."
  }
}

variable "allowed_frontend_origins" {
  type        = list(string)
  description = "Exact HTTPS origins allowed by the realtime WebSocket service."
  validation {
    condition     = length(var.allowed_frontend_origins) > 0 && alltrue([for origin in var.allowed_frontend_origins : can(regex("^https://[^/]+$", origin))])
    error_message = "Provide one or more HTTPS frontend origins without paths."
  }
}

variable "vodex_credentials_secret_arn" {
  type        = string
  default     = ""
  description = "Optional Secrets Manager JSON secret with VODEX_API_KEY and VODEX_ACCOUNT_URL fields for the integration service."
  sensitive   = true
  validation {
    condition     = var.vodex_credentials_secret_arn == "" || can(regex(":secretsmanager:[^:]+:[0-9]{12}:secret:", var.vodex_credentials_secret_arn))
    error_message = "vodex_credentials_secret_arn must be empty or a Secrets Manager secret ARN."
  }
}

variable "oidc_issuer" {
  type        = string
  description = "Public issuer URL used by the central OIDC provider."
}

variable "oidc_jwks_url" {
  type        = string
  description = "Network-reachable JWKS URL used by the gateway."
}

variable "container_images" {
  type        = map(string)
  description = "Image URI for each service. Use immutable, digest-pinned images."
  validation {
    condition     = alltrue([for name in ["api-gateway", "compliance-api", "ai-runtime", "integration-service", "webhook-gateway", "telemetry-service", "realtime-service", "event-consumer"] : contains(keys(var.container_images), name)])
    error_message = "Provide an immutable image URI for every required backend and workflow service. Celery worker and beat reuse the compliance-api image with dedicated commands."
  }
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "ecs_service_max_capacity" {
  type        = number
  default     = 2
  description = "Maximum Fargate tasks per service for CPU target tracking. Increase only after reviewing expected AWS spend."
  validation {
    condition     = var.ecs_service_max_capacity >= 1 && var.ecs_service_max_capacity <= 10
    error_message = "ecs_service_max_capacity must be between 1 and 10."
  }
}

variable "db_name" {
  type    = string
  default = "opsbridge"
}

variable "db_username" {
  type    = string
  default = "opsbridge_admin"
}

variable "tags" {
  type    = map(string)
  default = { Project = "OpsBridge", ManagedBy = "Terraform" }
}
