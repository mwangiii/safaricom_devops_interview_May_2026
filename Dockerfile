# ─── Stage 1: Build dependencies ────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies into isolated directory
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ─── Stage 2: Production runtime ─────────────────────────────────────────────
FROM python:3.11-slim AS production

LABEL maintainer="devops@safaricom.example.com"
LABEL org.opencontainers.image.source="https://github.com/safaricom/auth-api"

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home --shell /bin/false appuser

WORKDIR /app

# Copy application source
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup config.py run.py ./

# Create necessary runtime directories
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app/logs

# Drop to non-root
USER appuser

# Expose application port
EXPOSE 5000

# Healthcheck — calls the /health endpoint every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Use Gunicorn for production WSGI serving
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--worker-connections", "1000", \
     "--timeout", "60", \
     "--keep-alive", "5", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "run:app"]