variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Deployment environment (staging | production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be 'staging' or 'production'."
  }
}

variable "project" {
  description = "Project identifier used for resource naming and tagging"
  type        = string
  default     = "safaricom-auth"
}

# ── Networking ─────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "availability_zones" {
  description = "AZs to use (must match subnet count)"
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b"]
}

# ── Compute ────────────────────────────────────────────────────────────────────

variable "container_image" {
  description = "Full Docker image URI including tag"
  type        = string
  # e.g. "123456789.dkr.ecr.eu-west-1.amazonaws.com/safaricom-auth-api:sha-abc1234"
}

variable "container_port" {
  description = "Port the Flask container listens on"
  type        = number
  default     = 5000
}

variable "task_cpu" {
  description = "ECS task CPU units (256 = 0.25 vCPU)"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "ECS task memory in MiB"
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Desired number of running ECS tasks"
  type        = number
  default     = 2
}

# ── Database ───────────────────────────────────────────────────────────────────

variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "safaricom_auth"
}

variable "db_username" {
  description = "PostgreSQL master username (stored in Secrets Manager)"
  type        = string
  default     = "dbadmin"
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for RDS (GiB)"
  type        = number
  default     = 20
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "db_multi_az" {
  description = "Enable RDS Multi-AZ for high availability"
  type        = bool
  default     = false
}

# ── Secrets ────────────────────────────────────────────────────────────────────

variable "flask_secret_key_arn" {
  description = "ARN of the Secrets Manager secret holding FLASK SECRET_KEY"
  type        = string
}

variable "jwt_secret_key_arn" {
  description = "ARN of the Secrets Manager secret holding JWT_SECRET_KEY"
  type        = string
}
