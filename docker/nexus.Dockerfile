FROM python:3.13-slim

ARG NEXUS_VERSION=latest

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXUS_HOST=0.0.0.0 \
    NEXUS_PROFILE=full \
    NEXUS_PORT=2026 \
    NEXUS_DATA_DIR=/app/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

RUN if [ "$NEXUS_VERSION" = "latest" ]; then \
      uv pip install --system nexus-ai-fs; \
    else \
      uv pip install --system "nexus-ai-fs==${NEXUS_VERSION}"; \
    fi

RUN useradd -r -m -u 1000 -s /bin/bash nexus \
    && mkdir -p /app/data \
    && chown -R nexus:nexus /app

USER nexus

EXPOSE 2026

CMD nexusd \
    --host ${NEXUS_HOST} \
    --port ${NEXUS_PORT} \
    --data-dir ${NEXUS_DATA_DIR} \
    ${NEXUS_PROFILE:+--profile $NEXUS_PROFILE} \
    ${NEXUS_DATABASE_URL:+--database-url $NEXUS_DATABASE_URL} \
    ${NEXUS_AUTH_TYPE:+--auth-type $NEXUS_AUTH_TYPE} \
    ${NEXUS_API_KEY:+--api-key $NEXUS_API_KEY}
