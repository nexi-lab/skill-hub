#!/usr/bin/env bash

set -euo pipefail

SKILLHUB_URL="${SKILLHUB_URL:-http://localhost:8040}"
PACKAGE_DIR="${PACKAGE_DIR:-/workspace/examples/hello-skill}"

echo "==> Probe skill-hub"
curl -sS "${SKILLHUB_URL}/health"
echo

echo "==> Probe Nexus config"
curl -sS "${SKILLHUB_URL}/v1/nexus"
echo

echo "==> Register local package"
curl -sS -X POST "${SKILLHUB_URL}/v1/packages/register-local" \
  -H "content-type: application/json" \
  -d "{\"source_dir\":\"${PACKAGE_DIR}\"}"
echo

echo "==> Search package catalog"
curl -sS "${SKILLHUB_URL}/v1/packages/search?q=hello&limit=5"
echo

echo "==> Preview install"
curl -sS -X POST "${SKILLHUB_URL}/v1/installations/preview" \
  -H "content-type: application/json" \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
echo

echo "==> Install package"
curl -sS -X POST "${SKILLHUB_URL}/v1/installations" \
  -H "content-type: application/json" \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
echo

echo "==> Read published artifact file"
curl -sS "${SKILLHUB_URL}/v1/packages/nexi-lab/hello-skill/0.1.0/content?path=SKILL.md"
echo
