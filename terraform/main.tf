terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — replace bucket/key/region with your values
  backend "s3" {
    bucket         = "safaricom-terraform-state"
    key            = "auth-api/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "safaricom-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# ── Data sources ───────────────────────────────────────────────────────────────
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── Local values ───────────────────────────────────────────────────────────────
locals {
  prefix = "${var.project}-${var.environment}"

  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Repository  = "safaricom/auth-api"
  }
}
