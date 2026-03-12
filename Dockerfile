FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY docs/ ./docs/
COPY examples/ ./examples/
COPY scripts/ ./scripts/

RUN uv sync --frozen --no-dev

EXPOSE 8040

CMD ["skillhub", "serve", "--host", "0.0.0.0", "--port", "8040"]
