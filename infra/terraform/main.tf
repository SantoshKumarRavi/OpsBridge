data "aws_caller_identity" "current" {}

locals {
  services = {
    "api-gateway"         = { port = 8080, cpu = 512, memory = 1024, image_key = "api-gateway" }
    "compliance-api"      = { port = 8001, cpu = 1024, memory = 2048, image_key = "compliance-api" }
    "ai-runtime"          = { port = 8002, cpu = 1024, memory = 3072, image_key = "ai-runtime" }
    "integration-service" = { port = 8083, cpu = 512, memory = 1024, image_key = "integration-service" }
    "webhook-gateway"     = { port = 8787, cpu = 512, memory = 1024, image_key = "webhook-gateway" }
    "telemetry-service"   = { port = 8090, cpu = 256, memory = 512, image_key = "telemetry-service" }
    "celery-worker"       = { port = null, cpu = 1024, memory = 2048, image_key = "compliance-api", command = ["opentelemetry-instrument", "celery", "-A", "config", "worker", "-l", "INFO", "--concurrency=2"] }
    "celery-beat"         = { port = null, cpu = 512, memory = 1024, image_key = "compliance-api", command = ["opentelemetry-instrument", "celery", "-A", "config", "beat", "-l", "INFO"] }
    "realtime-service"    = { port = 8091, cpu = 512, memory = 1024, image_key = "realtime-service" }
    "event-consumer"      = { port = 8092, cpu = 512, memory = 1024, image_key = "event-consumer" }
  }
  discovery_services        = { for name, service in local.services : name => service if service.port != null }
  autoscaled_services       = { for name, service in local.services : name => service if !contains(["celery-worker", "celery-beat", "event-consumer"], name) }
  document_storage_services = { for name, service in local.services : name => service if contains(["compliance-api", "celery-worker"], name) }
}

resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb"
  description = "Public HTTPS entry only"
  vpc_id      = var.vpc_id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = var.tags
}

resource "aws_security_group" "service" {
  name        = "${var.project_name}-services"
  description = "OpsBridge service network"
  vpc_id      = var.vpc_id
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  ingress {
    from_port       = 8091
    to_port         = 8091
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = var.tags
}

resource "aws_security_group" "database" {
  name        = "${var.project_name}-postgres"
  description = "Postgres from OpsBridge tasks only"
  vpc_id      = var.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.service.id]
  }
  tags = var.tags
}

resource "aws_db_subnet_group" "database" {
  name       = "${var.project_name}-postgres"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_db_instance" "database" {
  identifier                      = "${var.project_name}-postgres"
  engine                          = "postgres"
  engine_version                  = "17.2"
  instance_class                  = var.db_instance_class
  allocated_storage               = 20
  max_allocated_storage           = 100
  storage_encrypted               = true
  db_name                         = var.db_name
  username                        = var.db_username
  manage_master_user_password     = true
  db_subnet_group_name            = aws_db_subnet_group.database.name
  vpc_security_group_ids          = [aws_security_group.database.id]
  publicly_accessible             = false
  multi_az                        = false
  backup_retention_period         = 7
  deletion_protection             = true
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.project_name}-final"
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  auto_minor_version_upgrade      = true
  tags                            = var.tags
}

resource "aws_s3_bucket" "documents" {
  bucket        = "${var.project_name}-${data.aws_caller_identity.current.account_id}-${var.aws_region}-documents"
  force_destroy = false
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}

resource "aws_sqs_queue" "domain_events_dlq" {
  name                      = "${var.project_name}-domain-events-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = var.tags
}

resource "aws_sqs_queue" "domain_events" {
  name                       = "${var.project_name}-domain-events"
  visibility_timeout_seconds = 120
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.domain_events_dlq.arn
    maxReceiveCount     = 5
  })
  tags = var.tags
}

resource "aws_sns_topic" "notifications" {
  name              = "${var.project_name}-notifications"
  kms_master_key_id = "alias/aws/sns"
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "services" {
  for_each          = local.services
  name              = "/ecs/${var.project_name}/${each.key}"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_ecs_cluster" "main" {
  name = var.project_name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = var.tags
}

resource "aws_service_discovery_private_dns_namespace" "services" {
  name        = "opsbridge.local"
  vpc         = var.vpc_id
  description = "Private service discovery for OpsBridge"
}

resource "aws_service_discovery_service" "services" {
  for_each = local.discovery_services
  name     = each.key
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.services.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
  health_check_custom_config { failure_threshold = 1 }
}

resource "aws_iam_role" "task_execution" {
  name = "${var.project_name}-task-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "read-runtime-secrets"
  role = aws_iam_role.task_execution.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue", "kms:Decrypt"], Resource = concat([aws_db_instance.database.master_user_secret[0].secret_arn, var.internal_service_token_secret_arn, var.rate_limit_redis_url_secret_arn, var.rabbitmq_url_secret_arn, var.celery_redis_url_secret_arn, var.realtime_redis_url_secret_arn, var.realtime_ticket_secret_arn], var.vodex_credentials_secret_arn == "" ? [] : [var.vodex_credentials_secret_arn]) }]
  })
}

resource "aws_iam_role" "task" {
  for_each           = local.services
  name               = "${var.project_name}-${each.key}-task"
  assume_role_policy = aws_iam_role.task_execution.assume_role_policy
}

resource "aws_iam_role_policy" "task_access" {
  for_each = local.document_storage_services
  name     = "document-storage-access"
  role     = aws_iam_role.task[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = ["${aws_s3_bucket.documents.arn}/*"] },
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = [aws_s3_bucket.documents.arn] }
    ]
  })
}

resource "aws_lb" "api" {
  name               = "${var.project_name}-api"
  load_balancer_type = "application"
  internal           = false
  subnets            = var.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]
  tags               = var.tags
}

resource "aws_lb_target_group" "gateway" {
  name        = "${var.project_name}-gateway"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
  tags = var.tags
}

resource "aws_lb_target_group" "realtime" {
  name        = "${var.project_name}-realtime"
  port        = 8091
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
  tags = var.tags
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.gateway.arn
  }
}

resource "aws_lb_listener_rule" "realtime_websocket" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.realtime.arn
  }
  condition {
    path_pattern { values = ["/ws/*"] }
  }
  tags = var.tags
}

resource "aws_ecs_task_definition" "service" {
  for_each                 = local.services
  family                   = "${var.project_name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task[each.key].arn
  container_definitions = jsonencode([merge({
    name         = each.key
    image        = var.container_images[each.value.image_key]
    essential    = true
    portMappings = each.value.port == null ? [] : [{ containerPort = each.value.port, hostPort = each.value.port, protocol = "tcp" }]
    environment = concat(
      [
        { name = "APP_ENV", value = "production" },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "S3_BUCKET", value = aws_s3_bucket.documents.bucket },
        { name = "USE_S3", value = "true" },
        { name = "POSTGRES_DB", value = var.db_name },
        { name = "POSTGRES_HOST", value = aws_db_instance.database.address },
        { name = "POSTGRES_PORT", value = tostring(aws_db_instance.database.port) },
        { name = "POSTGRES_SECRET_ARN", value = aws_db_instance.database.master_user_secret[0].secret_arn },
        { name = "INTERNAL_SERVICE_TOKEN_SECRET_ARN", value = var.internal_service_token_secret_arn },
        { name = "OIDC_ISSUER", value = var.oidc_issuer },
        { name = "OIDC_JWKS_URL", value = var.oidc_jwks_url },
        { name = "OIDC_AUDIENCE", value = "opsbridge-api" },
        { name = "DEV_IDENTITY_ENABLED", value = "false" },
        { name = "COMPLIANCE_SERVICE_URL", value = "http://compliance-api.opsbridge.local:8001" },
        { name = "AI_SERVICE_URL", value = "http://ai-runtime.opsbridge.local:8002" },
        { name = "INTEGRATION_SERVICE_URL", value = "http://integration-service.opsbridge.local:8083" },
        { name = "TELEMETRY_SERVICE_URL", value = "http://telemetry-service.opsbridge.local:8090" },
        { name = "KAFKA_BOOTSTRAP_SERVERS", value = var.kafka_bootstrap_servers },
        { name = "KAFKA_SECURITY_PROTOCOL", value = var.kafka_security_protocol },
        { name = "REALTIME_SERVICE_URL", value = "http://realtime-service.opsbridge.local:8091" }
      ],
      each.key == "ai-runtime" ? [
        { name = "AGENT_MEMORY_BACKEND", value = "postgres" },
        { name = "AGENT_MEMORY_TTL_DAYS", value = "30" },
        { name = "AGENT_MEMORY_CLEANUP_INTERVAL_SECONDS", value = "3600" },
        { name = "LANGGRAPH_STRICT_MSGPACK", value = "true" },
        { name = "COMPLIANCE_API_BASE_URL", value = "http://compliance-api.opsbridge.local:8001" }
      ] : [],
      contains(["compliance-api", "celery-worker", "celery-beat"], each.key) ? [
        { name = "MEDIA_ROOT", value = "/tmp/opsbridge-uploads" },
        { name = "REALTIME_SERVICE_URL", value = "http://realtime-service.opsbridge.local:8091" }
      ] : [],
      each.key == "api-gateway" ? [
        { name = "REALTIME_WS_URL", value = "${replace(var.public_api_origin, "https://", "wss://")}/ws/cases" },
      ] : [],
      each.key == "realtime-service" ? [
        { name = "PORT", value = "8091" },
        { name = "ALLOWED_ORIGINS", value = join(",", var.allowed_frontend_origins) }
      ] : [],
      each.key == "event-consumer" ? [
        { name = "PORT", value = "8092" },
        { name = "KAFKA_GROUP_ID", value = "opsbridge-case-projection-v1" }
      ] : []
    )
    secrets = concat(
      contains(["compliance-api", "ai-runtime", "celery-worker", "celery-beat"], each.key) ? [{ name = "POSTGRES_MASTER_SECRET_JSON", valueFrom = aws_db_instance.database.master_user_secret[0].secret_arn }] : [],
      contains(["api-gateway", "compliance-api", "ai-runtime", "integration-service", "celery-worker", "celery-beat"], each.key) ? [{ name = "INTERNAL_SERVICE_TOKEN", valueFrom = var.internal_service_token_secret_arn }] : [],
      each.key == "integration-service" && var.vodex_credentials_secret_arn != "" ? [
        { name = "VODEX_API_KEY", valueFrom = "${var.vodex_credentials_secret_arn}:VODEX_API_KEY::" },
        { name = "VODEX_ACCOUNT_URL", valueFrom = "${var.vodex_credentials_secret_arn}:VODEX_ACCOUNT_URL::" }
      ] : [],
      each.key == "api-gateway" ? [
        { name = "RATE_LIMIT_REDIS_URL", valueFrom = var.rate_limit_redis_url_secret_arn },
        { name = "REALTIME_TICKET_SECRET", valueFrom = var.realtime_ticket_secret_arn }
      ] : [],
      contains(["compliance-api", "celery-worker", "celery-beat"], each.key) ? [
        { name = "RABBITMQ_URL", valueFrom = var.rabbitmq_url_secret_arn },
        { name = "REDIS_URL", valueFrom = var.celery_redis_url_secret_arn },
        { name = "REALTIME_TICKET_SECRET", valueFrom = var.realtime_ticket_secret_arn }
      ] : [],
      each.key == "realtime-service" ? [
        { name = "REDIS_URL", valueFrom = var.realtime_redis_url_secret_arn },
        { name = "REALTIME_TICKET_SECRET", valueFrom = var.realtime_ticket_secret_arn },
        { name = "INTERNAL_SERVICE_TOKEN", valueFrom = var.internal_service_token_secret_arn }
      ] : [],
      each.key == "event-consumer" ? [
        { name = "POSTGRES_MASTER_SECRET_JSON", valueFrom = aws_db_instance.database.master_user_secret[0].secret_arn }
      ] : []
    )
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.services[each.key].name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "task" } }
  }, try(each.value.command, null) == null ? {} : { command = each.value.command })])
}

resource "aws_ecs_service" "service" {
  for_each                           = local.services
  name                               = each.key
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.service[each.key].arn
  desired_count                      = 1
  launch_type                        = "FARGATE"
  enable_execute_command             = false
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }
  dynamic "service_registries" {
    for_each = each.value.port == null ? [] : [1]
    content { registry_arn = aws_service_discovery_service.services[each.key].arn }
  }
  lifecycle {
    # Application Auto Scaling owns desired_count after service creation.
    ignore_changes = [desired_count]
  }
  dynamic "load_balancer" {
    for_each = contains(["api-gateway", "realtime-service"], each.key) ? [1] : []
    content {
      target_group_arn = each.key == "api-gateway" ? aws_lb_target_group.gateway.arn : aws_lb_target_group.realtime.arn
      container_name   = each.key
      container_port   = each.value.port
    }
  }
  depends_on = [aws_lb_listener.https, aws_lb_listener_rule.realtime_websocket, aws_iam_role_policy_attachment.task_execution]
  tags       = var.tags
}

resource "aws_appautoscaling_target" "service" {
  for_each           = local.autoscaled_services
  max_capacity       = var.ecs_service_max_capacity
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.service[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "service_cpu" {
  for_each           = local.autoscaled_services
  name               = "${var.project_name}-${each.key}-cpu-target"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.service[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.service[each.key].scalable_dimension
  service_namespace  = aws_appautoscaling_target.service[each.key].service_namespace
  target_tracking_scaling_policy_configuration {
    target_value       = 70
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
