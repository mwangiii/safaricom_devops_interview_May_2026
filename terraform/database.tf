# ── DB Subnet Group (private subnets only) ─────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name        = "${local.prefix}-db-subnet-group"
  description = "Private subnets for RDS — no public access"
  subnet_ids  = aws_subnet.private[*].id
  tags        = local.common_tags
}

# ── RDS Security Group (empty skeleton) ───────────────────────────────────────
resource "aws_security_group" "rds" {
  name        = "${local.prefix}-sg-rds"
  description = "RDS PostgreSQL security group — ingress handled via separate rules"
  vpc_id      = aws_vpc.main.id

  # No inline ingress/egress rules
  tags = merge(local.common_tags, { Name = "${local.prefix}-sg-rds" })
}

# ── Ingress rule: ECS → RDS (PostgreSQL) ──────────────────────────────────────
resource "aws_security_group_rule" "rds_ingress_from_ecs" {
  type                     = "ingress"
  description              = "PostgreSQL from ECS tasks only"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"

  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.ecs_tasks.id
}

# ──  Explicit deny-all egress is not required in AWS SGs
# Security Groups are stateful and default to allow all egress unless restricted.
# If you truly want strict egress control, define it explicitly:
resource "aws_security_group_rule" "rds_no_egress" {
  type              = "egress"
  security_group_id = aws_security_group.rds.id

  from_port   = 0
  to_port     = 0
  protocol    = "-1"
  cidr_blocks = []
}

# ── RDS Parameter Group ────────────────────────────────────────────────────────
resource "aws_db_parameter_group" "postgres" {
  name        = "${local.prefix}-pg15"
  family      = "postgres15"
  description = "Custom parameter group for ${local.prefix}"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = local.common_tags
}

# ── RDS Instance ───────────────────────────────────────────────────────────────
resource "aws_db_instance" "postgres" {
  identifier        = "${local.prefix}-db"
  engine            = "postgres"
  engine_version    = var.db_engine_version
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.postgres.name

  publicly_accessible = false
  multi_az            = var.db_multi_az

  backup_retention_period = 7
  backup_window           = "02:00-03:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  deletion_protection       = var.environment == "production"
  skip_final_snapshot       = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${local.prefix}-final-snapshot" : null

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  auto_minor_version_upgrade = true

  tags = local.common_tags
}

# ── Store DB connection URL in Secrets Manager ─────────────────────────────────
resource "aws_secretsmanager_secret" "db_url" {
  name                    = "${local.prefix}/${var.environment}/database-url"
  description             = "PostgreSQL connection URL for the auth API"
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "db_url" {
  secret_id = aws_secretsmanager_secret.db_url.id

  secret_string = "postgresql://${var.db_username}:MANAGED_BY_RDS@${aws_db_instance.postgres.endpoint}/${var.db_name}?sslmode=require"

  lifecycle {
    ignore_changes = [secret_string]
  }
}