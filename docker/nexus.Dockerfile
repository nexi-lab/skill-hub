ARG NEXUS_IMAGE=ghcr.io/nexi-lab/nexus:0.9.2
FROM ${NEXUS_IMAGE}

USER root

# ghcr.io/nexi-lab/nexus:0.9.2 is missing libgomp at runtime, which makes
# txtai/ggml import fail even though the Python packages are present.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY docker/nexus.skillhub.yaml /app/configs/config.skillhub.yaml

USER nexus
