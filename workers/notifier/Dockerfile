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
COPY workers/notifier ./workers/notifier

# Install production dependencies into a virtual environment
RUN uv venv /opt/venv && \
    uv pip install --no-cache --python /opt/venv/bin/python ./libs/common ./workers/notifier

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
COPY workers/notifier/app ./app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

CMD ["python", "-m", "app.main"]
