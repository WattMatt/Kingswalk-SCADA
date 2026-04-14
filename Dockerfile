# syntax=docker/dockerfile:1

# ─── Stage 1: dependencies ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy only the dependency manifest first — maximises layer cache hit rate.
COPY api/pyproject.toml ./
# hatchling requires the package directory to exist at install time.
COPY api/app ./app

# Install production dependencies (no dev extras).
RUN pip install --no-cache-dir .

# ─── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Suppress .pyc file generation and enable unbuffered stdout/stderr.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy installed packages from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source.
COPY api/app ./app

EXPOSE 8080

# $PORT is set automatically by Railway; fall back to 8080 for local runs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
