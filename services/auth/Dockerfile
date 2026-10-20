# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.1 /uv /uvx /bin/

# Copy workspace configuration and packages
COPY pyproject.toml .python-version ./
COPY libs/common ./libs/common
COPY services/auth ./services/auth

# Install production dependencies into a virtual environment
RUN uv venv /opt/venv && \
    uv pip install --no-cache --python /opt/venv/bin/python ./libs/common ./services/auth

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
COPY services/auth/app ./app
COPY services/auth/migrations ./migrations
COPY services/auth/alembic.ini ./

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
