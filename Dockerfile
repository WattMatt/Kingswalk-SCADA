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

# Install Doppler CLI — used to inject secrets at startup when DOPPLER_TOKEN is set.
# Uses official apt repo with GPG verification (not curl-pipe-sh).
RUN apt-get update && \
    apt-get install -y --no-install-recommends apt-transport-https ca-certificates curl gnupg && \
    curl -1sLf "https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key" | \
      gpg --dearmor -o /usr/share/keyrings/doppler-cli-archive-keyring.gpg && \
    curl -1sLf "https://packages.doppler.com/public/cli/config.deb.txt?distro=debian&codename=bookworm" \
      > /etc/apt/sources.list.d/doppler-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends doppler && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 8080

# When DOPPLER_TOKEN is set: Doppler injects secrets, then starts uvicorn.
# When not set: uvicorn starts directly, reading secrets from env vars (Railway native integration
# or local .env via pydantic-settings).
CMD ["sh", "-c", \
  "if [ -n \"$DOPPLER_TOKEN\" ]; then \
     exec doppler run -- uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8080}\"; \
   else \
     exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8080}\"; \
   fi"]
