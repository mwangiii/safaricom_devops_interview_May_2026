# ── ECS Cluster ────────────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "${local.prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.common_tags
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.prefix}/api"
  retention_in_days = 30
  tags              = local.common_tags
}

# ── ECS Task Definition ────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "api" {
  family                   = "${local.prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.container_image
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      secrets = [
        { name = "SECRET_KEY",     valueFrom = var.flask_secret_key_arn },
        { name = "JWT_SECRET_KEY", valueFrom = var.jwt_secret_key_arn },
        { name = "DATABASE_URL",   valueFrom = aws_secretsmanager_secret.db_url.arn }
      ]

      environment = [
        { name = "FLASK_ENV", value = var.environment }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port}/health || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 20
      }

      readonlyRootFilesystem = true
      user                   = "1001:1001"
    }
  ])

  tags = local.common_tags
}

# ── Application Load Balancer ─────────────────────────────────────────────────
resource "aws_lb" "api" {
  name               = "${local.prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.environment == "production"
  drop_invalid_header_fields = true

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "alb"
    enabled = true
  }

  tags = local.common_tags
}

resource "aws_lb_target_group" "api" {
  name        = "${local.prefix}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 10
    matcher             = "200"
  }

  tags = local.common_tags
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.api.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# ── ECS Service ────────────────────────────────────────────────────────────────
resource "aws_ecs_service" "api" {
  name                              = "${local.prefix}-api"
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.api.arn
  desired_count                     = var.desired_count
  launch_type                       = "FARGATE"
  platform_version                  = "LATEST"
  health_check_grace_period_seconds = 30
  enable_execute_command            = false

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.container_port
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_controller {
    type = "ECS"
  }

  tags = local.common_tags

  depends_on = [aws_lb_listener.https]
}

# ── Auto Scaling ───────────────────────────────────────────────────────────────
resource "aws_appautoscaling_target" "api" {
  max_capacity       = 10
  min_capacity       = var.desired_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "${local.prefix}-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 70.0

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }

    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# ── SECURITY GROUPS (SKELETONS ONLY) ───────────────────────────────────────────

resource "aws_security_group" "alb" {
  name        = "${local.prefix}-sg-alb"
  description = "ALB security group (rules managed separately)"
  vpc_id      = aws_vpc.main.id

  tags = merge(local.common_tags, { Name = "${local.prefix}-sg-alb" })
}

resource "aws_security_group" "ecs_tasks" {
  name        = "${local.prefix}-sg-ecs"
  description = "ECS tasks security group (rules managed separately)"
  vpc_id      = aws_vpc.main.id

  tags = merge(local.common_tags, { Name = "${local.prefix}-sg-ecs" })
}

# ── SECURITY GROUP RULES ──────────────────────────────────────────────────────

# ALB inbound HTTP/HTTPS from internet
resource "aws_security_group_rule" "alb_https_in" {
  type              = "ingress"
  security_group_id = aws_security_group.alb.id

  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb_http_in" {
  type              = "ingress"
  security_group_id = aws_security_group.alb.id

  from_port   = 80
  to_port     = 80
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}

# ALB → ECS
resource "aws_security_group_rule" "alb_to_ecs" {
  type                     = "egress"
  security_group_id        = aws_security_group.alb.id

  from_port                = var.container_port
  to_port                  = var.container_port
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ecs_tasks.id
}

# ECS ← ALB
resource "aws_security_group_rule" "ecs_from_alb" {
  type                     = "ingress"
  security_group_id        = aws_security_group.ecs_tasks.id

  from_port                = var.container_port
  to_port                  = var.container_port
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
}

# ECS → Internet (HTTPS)
resource "aws_security_group_rule" "ecs_https_out" {
  type              = "egress"
  security_group_id = aws_security_group.ecs_tasks.id

  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}

# ECS → RDS
resource "aws_security_group_rule" "ecs_to_rds" {
  type                     = "egress"
  security_group_id        = aws_security_group.ecs_tasks.id

  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.rds.id
}

# ── S3 bucket for ALB logs ─────────────────────────────────────────────────────
resource "aws_s3_bucket" "alb_logs" {
  bucket        = "${local.prefix}-alb-logs-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.environment != "production"
  tags          = local.common_tags
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
  id     = "expire-logs"
  status = "Enabled"

   filter {}  

    expiration {
      days = 90
    }
  }
}

# ── ACM Certificate ───────────────────────────────────────────────────────────
resource "aws_acm_certificate" "api" {
  domain_name       = "${var.environment == "production" ? "" : "${var.environment}."}auth.safaricom.example.com"
  validation_method = "DNS"

  tags = local.common_tags

  lifecycle {
    create_before_destroy = true
  }
}