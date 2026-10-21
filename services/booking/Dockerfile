# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.1 /uv /uvx /bin/

# Copy workspace configuration and packages
COPY pyproject.toml .python-version ./
COPY libs/common ./libs/common
COPY services/booking ./services/booking

# Build wheel for common and install packages into a virtual environment
RUN uv build --wheel libs/common --out-dir /dist && \
    uv venv /opt/venv && \
    uv pip install --no-cache --python /opt/venv/bin/python --no-sources /dist/*.whl ./services/booking

# ==============================================================================
# Production runtime image
# ==============================================================================
FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/bash -m appuser

# Copy virtualenv and application code
COPY --from=builder /opt/venv /opt/venv
COPY libs/common/ticketrush_common ./ticketrush_common
COPY services/booking/app ./app
COPY services/booking/migrations ./migrations
COPY services/booking/alembic.ini ./

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8003

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2", "--limit-concurrency", "2000"]
