# SAFARICOM AUTH API

A production-grade Flask + PostgreSQL authentication API with JWT-based auth, user and organisation management, containerised with Docker, deployed via GitHub Actions CI/CD, and provisioned on AWS with Terraform.

---

## Architecture Overview

```
Internet
    │
    ▼
[Route 53]
    │ HTTPS
    ▼
[Application Load Balancer]  ← public subnets (AZ-a, AZ-b)
    │
    ▼  (HTTP on container port 5000)
[ECS Fargate Service]        ← private subnets
  └─ Task: Flask API (Gunicorn, non-root, read-only FS)
    │         │
    │         └─── [CloudWatch Logs]
    │
    ▼  (PostgreSQL 5432, TLS enforced)
[RDS PostgreSQL 15]          ← private subnets (Multi-AZ in prod)
    │
    └─── [Secrets Manager]   ← DB URL, Flask SECRET_KEY, JWT_SECRET_KEY
         [KMS]               ← Secrets encryption at rest
```

**Key design decisions:**
- ECS tasks run in **private subnets** - zero internet exposure
- RDS has `publicly_accessible = false` and accepts connections only from the ECS security group
- No IAM wildcard policies; GitHub Actions uses OIDC (no long-lived access keys)
- Secrets Manager secrets are fetched at task launch - never baked into images or environment variables at build time
- ALB enforces TLS 1.2+ and drops invalid headers

---

## Local Development

### Prerequisites
- Docker ≥ 24, Docker Compose ≥ 2.20
- `openssl` (for generating secrets)

### 1. Create your `.env`
```bash
cp .env.example .env

# Generate strong secrets
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
sed -i "s/CHANGE_ME_USE_OPENSSL_RAND_HEX_32/$SECRET_KEY/" .env
# Repeat for JWT_SECRET_KEY and POSTGRES_PASSWORD
```

### 2. Start all services
```bash
docker-compose up --build
```

This brings up:
- **PostgreSQL** on `db:5432` (internal only)
- **Flask API** on `api:5000` (internal only)
- **Nginx** on `localhost:80` → `localhost:443` (proxies to Flask)

### 3. Verify
```bash
curl http://localhost/health
# → {"status": "healthy"}
```

### 4. Run tests locally
```bash
# Outside Docker
pip install -r requirements.txt pytest pytest-cov
export DATABASE_URL=postgresql://safaricom:yourpassword@localhost:5432/safaricom_auth
pytest tests/ -v --cov=app

# Inside Docker
docker-compose exec api pytest tests/ -v --cov=app
```

Pre-submission Validation
All configuration files have been statically validated on Ubuntu 24.04, Docker 27, Terraform 1.6+.
1. docker compose config 
![](assets/1.png)
![](assets/2.png)

2. docker build --no-cache --target production . --check
![](assets/3.png)

3. terraform validate
![](assets/4.png)

---

## CI/CD Pipeline

All stages are defined in `.github/workflows/ci-cd.yml`.

| Stage | Trigger | Description |
|-------|---------|-------------|
| **lint-test** | Every PR + push to `main`/`develop` | flake8 lint, `safety` dependency CVE scan, `bandit` SAST, pytest with coverage gate (≥80%) |
| **build-push** | Push to `main`/`develop` only | Multi-stage Docker build, tagged `sha-<short-sha>`, pushed to Docker Hub (or ECR) |
| **deploy-staging** | After successful build | Deploys to staging ECS cluster; runs smoke tests |
| **approve-prod** | After staging deploy | **Manual approval gate** - requires a reviewer in the `production-approval` GitHub Environment |
| **deploy-prod** | After approval | Deploys to production ECS; tags image `:stable` in the registry |
| **rollback** | Manual (`workflow_dispatch`) | Re-deploys a specified tag (defaults to `:stable`) to production |

### Secrets required in GitHub
```
DOCKERHUB_USERNAME      # or AWS_ACCOUNT_ID + AWS_REGION for ECR
DOCKERHUB_TOKEN
```

### Manual rollback
```
GitHub Actions → CI/CD Pipeline → Run workflow
  rollback_tag: sha-abc1234   ← leave blank to use :stable
```

---

## Infrastructure (Terraform)

### File structure
```
terraform/
  main.tf       # Provider, backend, locals
  variables.tf  # All input variables with validation
  vpc.tf        # VPC, subnets, IGW, NAT GWs, route tables, VPC flow logs
  compute.tf    # ECS cluster/service/task, ALB, auto-scaling, security groups
  database.tf   # RDS PostgreSQL, subnet group, parameter group, Secrets Manager
  iam.tf        # Task execution role, task role, flow log role, GitHub OIDC role, KMS
  outputs.tf    # ALB DNS, ECS names, RDS endpoint, secret ARNs
```

### Deploy
```bash
cd terraform

# Staging
terraform init
terraform workspace new staging
terraform apply -var="environment=staging" \
                -var="container_image=youraccount/safaricom-auth-api:sha-abc1234" \
                -var="flask_secret_key_arn=arn:aws:secretsmanager:..." \
                -var="jwt_secret_key_arn=arn:aws:secretsmanager:..."

# Production (requires explicit approval)
terraform workspace select production
terraform apply -var="environment=production" ...
```

---

## Assumptions

1. **DNS / ACM** - A hosted zone for `auth.safaricom.example.com` exists in Route 53. The ACM certificate resource is defined but DNS validation records must be created separately (or via `aws_route53_record` - omitted for brevity).
2. **Secrets pre-created** - `flask_secret_key_arn` and `jwt_secret_key_arn` reference secrets created outside Terraform (e.g. by a bootstrap script) to avoid storing secret values in Terraform state.
3. **ECR repository** - Assumed to exist; not created in these modules. The GitHub Actions workflow references Docker Hub by default.
4. **OIDC provider** - The GitHub Actions OIDC provider (`token.actions.githubusercontent.com`) is assumed to be registered in the AWS account.
5. **Nginx TLS** - The `docker-compose` setup uses a self-signed snakeoil cert for local development. In production, TLS is terminated at the ALB; Nginx is not present in the cloud deployment.
6. **App factory pattern** - `create_app()` is assumed to follow Flask's application factory pattern, accepting a config dict.

---

## One Improvement With More Time

**Implement secret rotation end-to-end.** Currently `manage_master_user_password = true` on RDS auto-rotates the DB password in Secrets Manager, but the `DATABASE_URL` secret (which combines host + password) is not automatically kept in sync. With more time I would wire a Lambda rotation function to re-build and re-store the `DATABASE_URL` secret whenever RDS rotates the master password, ensuring zero-downtime secret rotation without any manual intervention.
