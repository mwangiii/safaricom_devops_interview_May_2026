# -------------------- BUILD STAGE --------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# system deps (optional but safe for psycopg2 / builds)
RUN apt-get update && apt-get install -y build-essential

COPY requirements.txt .

# install dependencies into system path (not --user)
RUN pip install --no-cache-dir -r requirements.txt


# -------------------- RUNTIME STAGE --------------------
FROM python:3.11-slim

WORKDIR /app

# copy installed dependencies from builder
COPY --from=builder /usr/local /usr/local

# copy application code
COPY . .

# non-root user (security)
RUN useradd -m appuser
USER appuser

EXPOSE 5000

# production server
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "run:app"]