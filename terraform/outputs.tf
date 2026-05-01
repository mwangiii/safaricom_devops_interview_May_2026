output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.api.dns_name
}

output "alb_zone_id" {
  description = "Hosted zone ID of the ALB (for Route53 alias records)"
  value       = aws_lb.api.zone_id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.api.name
}

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port)"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "rds_instance_id" {
  description = "RDS instance identifier"
  value       = aws_db_instance.postgres.id
}

output "db_url_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the database URL"
  value       = aws_secretsmanager_secret.db_url.arn
  sensitive   = true
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for secrets encryption"
  value       = aws_kms_key.secrets.arn
  sensitive   = true
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC deployments"
  value       = aws_iam_role.github_actions_deploy.arn
}
