# ── Used by the ECS agent to pull images and write logs — NOT by application code.

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${local.prefix}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "ecs_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Attach AWS-managed policy for standard ECS execution tasks (ECR pull, CW logs)
resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow ECS agent to fetch the specific secrets needed at task launch
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "${local.prefix}-ecs-execution-secrets"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetTaskSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          var.flask_secret_key_arn,
          var.jwt_secret_key_arn,
          aws_secretsmanager_secret.db_url.arn
        ]
      },
      {
        Sid    = "DecryptSecrets"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = [aws_kms_key.secrets.arn]
      }
    ]
  })
}

# ── ECS Task Role ──────────────────────────────────────────────────────────────
# Used by the running application container — minimal permissions only.

resource "aws_iam_role" "ecs_task" {
  name               = "${local.prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "${local.prefix}-ecs-task-policy"
  role = aws_iam_role.ecs_task.id

  # Application needs no AWS API access beyond what the execution role provides.
  # Add only the minimum actions required as the app evolves (e.g. SES, S3).
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyWildcard"
        Effect = "Deny"
        Action = ["*"]
        Resource = ["*"]
        Condition = {
          StringNotEquals = {
            "aws:RequestedRegion" = var.aws_region
          }
        }
      }
    ]
  })
}

# ── VPC Flow Log Role ──────────────────────────────────────────────────────────
resource "aws_iam_role" "flow_log" {
  name               = "${local.prefix}-vpc-flow-log"
  assume_role_policy = data.aws_iam_policy_document.flow_log_trust.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "flow_log_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "flow_log" {
  name = "${local.prefix}-flow-log-policy"
  role = aws_iam_role.flow_log.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "${aws_cloudwatch_log_group.vpc_flow_log.arn}:*"
        ]
      }
    ]
  })
}

# ── KMS Key for Secrets Manager ────────────────────────────────────────────────
resource "aws_kms_key" "secrets" {
  description             = "${local.prefix} secrets encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${local.prefix}/secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# ── CI/CD Deployment Role ──────────────────────────────────────────────────────
# Assumed by GitHub Actions OIDC — no long-lived access keys needed.

resource "aws_iam_role" "github_actions_deploy" {
  name               = "${local.prefix}-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "github_oidc_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:safaricom/auth-api:*"]
    }
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "${local.prefix}-github-deploy-policy"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "*"
      },
      {
        Sid    = "ECSDeployService"
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:RegisterTaskDefinition"
        ]
        Resource = [
          aws_ecs_cluster.main.arn,
          aws_ecs_service.api.id
        ]
      },
      {
        Sid    = "PassExecutionRole"
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
      }
    ]
  })
}
