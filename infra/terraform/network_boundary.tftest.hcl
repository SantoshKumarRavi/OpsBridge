mock_provider "aws" {
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/opsbridge-mock"
    }
  }

  mock_resource "aws_db_instance" {
    defaults = {
      master_user_secret = [{
        secret_arn    = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:opsbridge-database"
        secret_status = "active"
      }]
    }
  }

  mock_resource "aws_lb" {
    defaults = {
      arn = "arn:aws:elasticloadbalancing:ap-south-1:123456789012:loadbalancer/app/opsbridge-api/0123456789abcdef"
    }
  }

  mock_resource "aws_lb_target_group" {
    defaults = {
      arn = "arn:aws:elasticloadbalancing:ap-south-1:123456789012:targetgroup/opsbridge-gateway/0123456789abcdef"
    }
  }

  mock_resource "aws_lb_listener" {
    defaults = {
      arn = "arn:aws:elasticloadbalancing:ap-south-1:123456789012:listener/app/opsbridge-api/0123456789abcdef/0123456789abcdef"
    }
  }

  mock_resource "aws_service_discovery_service" {
    defaults = {
      arn = "arn:aws:servicediscovery:ap-south-1:123456789012:service/srv-0123456789abcdef"
    }
  }
}

variables {
  vpc_id                            = "vpc-0123456789abcdef0"
  public_subnet_ids                 = ["subnet-public-a", "subnet-public-b"]
  private_subnet_ids                = ["subnet-private-a", "subnet-private-b"]
  certificate_arn                   = "arn:aws:acm:ap-south-1:123456789012:certificate/test"
  internal_service_token_secret_arn = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:internal-token"
  rate_limit_redis_url_secret_arn   = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:redis-url"
  rabbitmq_url_secret_arn           = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:rabbitmq-url"
  celery_redis_url_secret_arn       = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:celery-redis-url"
  realtime_redis_url_secret_arn     = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:realtime-redis-url"
  realtime_ticket_secret_arn        = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:realtime-ticket"
  kafka_bootstrap_servers           = "b-1.kafka.internal:9094,b-2.kafka.internal:9094"
  public_api_origin                 = "https://api.example.test"
  allowed_frontend_origins          = ["https://portal.example.test", "https://review.example.test"]
  oidc_issuer                       = "https://identity.example.test/realms/opsbridge"
  oidc_jwks_url                     = "https://identity.example.test/realms/opsbridge/protocol/openid-connect/certs"
  container_images = {
    "api-gateway"         = "public.ecr.aws/example/api-gateway:test"
    "compliance-api"      = "public.ecr.aws/example/compliance-api:test"
    "ai-runtime"          = "public.ecr.aws/example/ai-runtime:test"
    "integration-service" = "public.ecr.aws/example/integration-service:test"
    "webhook-gateway"     = "public.ecr.aws/example/webhook-gateway:test"
    "telemetry-service"   = "public.ecr.aws/example/telemetry-service:test"
    "realtime-service"    = "public.ecr.aws/example/realtime-service:test"
    "event-consumer"      = "public.ecr.aws/example/event-consumer:test"
  }
}

run "application_and_database_use_private_subnets" {
  command = apply

  assert {
    condition     = toset(aws_lb.api.subnets) == toset(var.public_subnet_ids)
    error_message = "The internet-facing ALB must use only the supplied public subnets."
  }

  assert {
    condition     = toset(aws_db_subnet_group.database.subnet_ids) == toset(var.private_subnet_ids)
    error_message = "PostgreSQL must use only the supplied private subnets."
  }

  assert {
    condition     = alltrue([for service in values(aws_ecs_service.service) : service.network_configuration[0].assign_public_ip == false])
    error_message = "ECS tasks must not receive public IP addresses."
  }

  assert {
    condition     = toset([for rule in aws_security_group.service.ingress : rule.from_port if try(contains(rule.security_groups, aws_security_group.alb.id), false)]) == toset([8080, 8091])
    error_message = "The ALB may reach only the API gateway and realtime WebSocket target ports."
  }
}

run "workflow_workers_and_realtime_are_wired" {
  command = apply

  assert {
    condition     = aws_ecs_service.service["celery-beat"].desired_count == 1 && !contains(keys(aws_appautoscaling_target.service), "celery-beat")
    error_message = "Celery beat must remain a single scheduler and must not receive CPU-based autoscaling that could start duplicate schedulers."
  }

  assert {
    condition     = jsondecode(aws_ecs_task_definition.service["celery-worker"].container_definitions)[0].command == ["opentelemetry-instrument", "celery", "-A", "config", "worker", "-l", "INFO", "--concurrency=2"] && length(jsondecode(aws_ecs_task_definition.service["celery-worker"].container_definitions)[0].portMappings) == 0
    error_message = "The Celery worker must run the worker command without an exposed application port."
  }

  assert {
    condition     = anytrue([for item in jsondecode(aws_ecs_task_definition.service["celery-worker"].container_definitions)[0].secrets : item.name == "RABBITMQ_URL" && item.valueFrom == var.rabbitmq_url_secret_arn]) && anytrue([for item in jsondecode(aws_ecs_task_definition.service["celery-worker"].container_definitions)[0].secrets : item.name == "REDIS_URL" && item.valueFrom == var.celery_redis_url_secret_arn])
    error_message = "The Celery worker must receive RabbitMQ and Redis connection strings from Secrets Manager."
  }

  assert {
    condition     = anytrue([for item in jsondecode(aws_ecs_task_definition.service["api-gateway"].container_definitions)[0].environment : item.name == "REALTIME_WS_URL" && item.value == "wss://api.example.test/ws/cases"])
    error_message = "The API gateway must advertise the HTTPS ALB's secure realtime WebSocket route."
  }

  assert {
    condition     = aws_lb_listener_rule.realtime_websocket.action[0].target_group_arn == aws_lb_target_group.realtime.arn && anytrue([for mapping in jsondecode(aws_ecs_task_definition.service["realtime-service"].container_definitions)[0].portMappings : mapping.containerPort == 8091])
    error_message = "The HTTPS listener must route the WebSocket path to the realtime ECS service on port 8091."
  }

  assert {
    condition     = anytrue([for item in jsondecode(aws_ecs_task_definition.service["event-consumer"].container_definitions)[0].secrets : item.name == "POSTGRES_MASTER_SECRET_JSON" && item.valueFrom == aws_db_instance.database.master_user_secret[0].secret_arn])
    error_message = "The Kafka projection consumer must use the same managed RDS credentials as the compliance API."
  }

  assert {
    condition     = toset(keys(aws_iam_role_policy.task_access)) == toset(["compliance-api", "celery-worker"])
    error_message = "Only the API and document worker may receive S3 document-bucket access; other ECS services must have separate task roles without that policy."
  }
}
