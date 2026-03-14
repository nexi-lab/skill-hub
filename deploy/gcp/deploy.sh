#!/usr/bin/env bash

set -euo pipefail

GCLOUD="${GCLOUD:-/opt/homebrew/share/google-cloud-sdk/bin/gcloud}"
PROJECT="${PROJECT:-nexi-lab-888}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
INSTANCE="${INSTANCE:-skill-hub-vm}"
ADDRESS="${ADDRESS:-skill-hub-ip}"
FIREWALL_RULE="${FIREWALL_RULE:-skill-hub-8040}"
NETWORK_TAG="${NETWORK_TAG:-skill-hub-http}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-4}"
BOOT_DISK_SIZE_GB="${BOOT_DISK_SIZE_GB:-50}"
IMAGE_FAMILY="${IMAGE_FAMILY:-debian-12}"
IMAGE_PROJECT="${IMAGE_PROJECT:-debian-cloud}"
STARTUP_SCRIPT="${STARTUP_SCRIPT:-deploy/gcp/startup.sh}"
LOCAL_REPO_DIR="${LOCAL_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
NEXUS_DEPLOY_MODE="${NEXUS_DEPLOY_MODE:-release}"
NEXUS_IMAGE="${NEXUS_IMAGE:-ghcr.io/nexi-lab/nexus:0.9.2}"
LOCAL_NEXUS_DIR="${LOCAL_NEXUS_DIR:-$(cd "${LOCAL_REPO_DIR}/.." && pwd)}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/skill-hub}"
REMOTE_ARCHIVE_PATH="${REMOTE_ARCHIVE_PATH:-/tmp/skill-hub.tgz}"
REMOTE_NEXUS_DIR="${REMOTE_NEXUS_DIR:-/opt/nexus-src}"
REMOTE_NEXUS_ARCHIVE_PATH="${REMOTE_NEXUS_ARCHIVE_PATH:-/tmp/nexus-src.tgz}"
TMP_ARCHIVE="$(python3 - <<'PY'
import os
import tempfile

fd, path = tempfile.mkstemp(prefix="skill-hub-deploy.", suffix=".tgz", dir="/tmp")
os.close(fd)
print(path)
PY
)"
TMP_NEXUS_ARCHIVE="$(python3 - <<'PY'
import os
import tempfile

fd, path = tempfile.mkstemp(prefix="nexus-deploy.", suffix=".tgz", dir="/tmp")
os.close(fd)
print(path)
PY
)"

cleanup() {
  rm -f "${TMP_ARCHIVE}"
  rm -f "${TMP_NEXUS_ARCHIVE}"
}
trap cleanup EXIT

TAR_ENV=(
  COPYFILE_DISABLE=1
  COPY_EXTENDED_ATTRIBUTES_DISABLE=1
)

"${GCLOUD}" services enable compute.googleapis.com --project "${PROJECT}"

if ! "${GCLOUD}" compute addresses describe "${ADDRESS}" \
  --project "${PROJECT}" \
  --region "${REGION}" >/dev/null 2>&1; then
  "${GCLOUD}" compute addresses create "${ADDRESS}" \
    --project "${PROJECT}" \
    --region "${REGION}"
fi

PUBLIC_IP="$("${GCLOUD}" compute addresses describe "${ADDRESS}" \
  --project "${PROJECT}" \
  --region "${REGION}" \
  --format='value(address)')"

if ! "${GCLOUD}" compute firewall-rules describe "${FIREWALL_RULE}" \
  --project "${PROJECT}" >/dev/null 2>&1; then
  "${GCLOUD}" compute firewall-rules create "${FIREWALL_RULE}" \
    --project "${PROJECT}" \
    --direction INGRESS \
    --network default \
    --action ALLOW \
    --rules tcp:8040 \
    --source-ranges 0.0.0.0/0 \
    --target-tags "${NETWORK_TAG}"
fi

env "${TAR_ENV[@]}" tar \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.DS_Store' \
  --exclude='._*' \
  --exclude='*/._*' \
  -C "${LOCAL_REPO_DIR}" \
  -czf "${TMP_ARCHIVE}" \
  .

if [[ "${NEXUS_DEPLOY_MODE}" == "source" ]]; then
  env "${TAR_ENV[@]}" tar \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='.DS_Store' \
    --exclude='._*' \
    --exclude='*/._*' \
    -C "${LOCAL_NEXUS_DIR}" \
    -czf "${TMP_NEXUS_ARCHIVE}" \
    Dockerfile \
    pyproject.toml \
    uv.lock \
    README.md \
    Cargo.toml \
    Cargo.lock \
    src \
    alembic \
    proto \
    rust \
    configs \
    scripts \
    data \
    dockerfiles
fi

if "${GCLOUD}" compute instances describe "${INSTANCE}" \
  --project "${PROJECT}" \
  --zone "${ZONE}" >/dev/null 2>&1; then
  "${GCLOUD}" compute instances add-metadata "${INSTANCE}" \
    --project "${PROJECT}" \
    --zone "${ZONE}" \
    --metadata-from-file startup-script="${STARTUP_SCRIPT}"
  "${GCLOUD}" compute instances reset "${INSTANCE}" \
    --project "${PROJECT}" \
    --zone "${ZONE}"
else
  "${GCLOUD}" compute instances create "${INSTANCE}" \
    --project "${PROJECT}" \
    --zone "${ZONE}" \
    --machine-type "${MACHINE_TYPE}" \
    --create-disk="auto-delete=yes,boot=yes,image-family=${IMAGE_FAMILY},image-project=${IMAGE_PROJECT},size=${BOOT_DISK_SIZE_GB},type=pd-balanced" \
    --address "${PUBLIC_IP}" \
    --tags "${NETWORK_TAG}" \
    --metadata-from-file startup-script="${STARTUP_SCRIPT}" \
    --labels "app=skill-hub,managed-by=codex"
fi

echo "skill-hub public health URL: http://${PUBLIC_IP}:8040/health"
echo "skill-hub docs URL:         http://${PUBLIC_IP}:8040/docs"

for _ in $(seq 1 60); do
  if "${GCLOUD}" compute ssh "${INSTANCE}" \
    --project "${PROJECT}" \
    --zone "${ZONE}" \
    --command "true" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

"${GCLOUD}" compute scp "${TMP_ARCHIVE}" "${INSTANCE}:${REMOTE_ARCHIVE_PATH}" \
  --project "${PROJECT}" \
  --zone "${ZONE}"

if [[ "${NEXUS_DEPLOY_MODE}" == "source" ]]; then
  "${GCLOUD}" compute scp "${TMP_NEXUS_ARCHIVE}" "${INSTANCE}:${REMOTE_NEXUS_ARCHIVE_PATH}" \
    --project "${PROJECT}" \
    --zone "${ZONE}"
fi

"${GCLOUD}" compute ssh "${INSTANCE}" \
  --project "${PROJECT}" \
  --zone "${ZONE}" \
  --command "
set -euo pipefail
sudo mkdir -p '${REMOTE_APP_DIR}'
sudo mkdir -p '${REMOTE_NEXUS_DIR}'
if sudo test -f '${REMOTE_APP_DIR}/.env'; then
  sudo cp '${REMOTE_APP_DIR}/.env' /tmp/skill-hub.env
fi
sudo find '${REMOTE_APP_DIR}' -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} +
sudo tar -xzf '${REMOTE_ARCHIVE_PATH}' -C '${REMOTE_APP_DIR}'
sudo find '${REMOTE_APP_DIR}' \\( -name '._*' -o -name '.DS_Store' \\) -delete
if [ '${NEXUS_DEPLOY_MODE}' = 'source' ]; then
  sudo find '${REMOTE_NEXUS_DIR}' -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  sudo tar -xzf '${REMOTE_NEXUS_ARCHIVE_PATH}' -C '${REMOTE_NEXUS_DIR}'
  sudo find '${REMOTE_NEXUS_DIR}' \\( -name '._*' -o -name '.DS_Store' \\) -delete
fi
if ! sudo test -f '${REMOTE_APP_DIR}/.env'; then
  api_key=\$(python3 -c 'import secrets; print(\"sk-\" + secrets.token_urlsafe(36))')
  sudo bash -lc \"cat >'${REMOTE_APP_DIR}/.env' <<EOF
NEXUS_API_KEY=\${api_key}
NEXUS_DEPLOY_MODE=${NEXUS_DEPLOY_MODE}
NEXUS_IMAGE=${NEXUS_IMAGE}
EOF\"
elif sudo test -f /tmp/skill-hub.env; then
  sudo mv /tmp/skill-hub.env '${REMOTE_APP_DIR}/.env'
fi
current_api_key=\$(sudo awk -F= '/^NEXUS_API_KEY=/{print \$2}' '${REMOTE_APP_DIR}/.env' | tail -n 1 || true)
if [ -z \"\${current_api_key}\" ] || [ \"\${current_api_key#sk-}\" = \"\${current_api_key}\" ] || [ \${#current_api_key} -lt 32 ]; then
  replacement_api_key=\$(python3 -c 'import secrets; print(\"sk-\" + secrets.token_urlsafe(36))')
  if sudo grep -q '^NEXUS_API_KEY=' '${REMOTE_APP_DIR}/.env'; then
    sudo sed -i \"s|^NEXUS_API_KEY=.*|NEXUS_API_KEY=\${replacement_api_key}|\" '${REMOTE_APP_DIR}/.env'
  else
    echo \"NEXUS_API_KEY=\${replacement_api_key}\" | sudo tee -a '${REMOTE_APP_DIR}/.env' >/dev/null
  fi
fi
if grep -q '^NEXUS_DEPLOY_MODE=' '${REMOTE_APP_DIR}/.env'; then
  sudo sed -i 's|^NEXUS_DEPLOY_MODE=.*|NEXUS_DEPLOY_MODE=${NEXUS_DEPLOY_MODE}|' '${REMOTE_APP_DIR}/.env'
else
  echo 'NEXUS_DEPLOY_MODE=${NEXUS_DEPLOY_MODE}' | sudo tee -a '${REMOTE_APP_DIR}/.env' >/dev/null
fi
if grep -q '^NEXUS_IMAGE=' '${REMOTE_APP_DIR}/.env'; then
  sudo sed -i 's|^NEXUS_IMAGE=.*|NEXUS_IMAGE=${NEXUS_IMAGE}|' '${REMOTE_APP_DIR}/.env'
else
  echo 'NEXUS_IMAGE=${NEXUS_IMAGE}' | sudo tee -a '${REMOTE_APP_DIR}/.env' >/dev/null
fi
compose_files=\"-f ${REMOTE_APP_DIR}/compose.yaml -f ${REMOTE_APP_DIR}/deploy/gcp/compose.gcp.yaml\"
if [ '${NEXUS_DEPLOY_MODE}' = 'source' ]; then
  compose_files=\"-f ${REMOTE_APP_DIR}/compose.yaml -f ${REMOTE_APP_DIR}/deploy/gcp/compose.nexus-source.yaml -f ${REMOTE_APP_DIR}/deploy/gcp/compose.gcp.yaml\"
fi
sudo docker compose \${compose_files} up -d postgres dragonfly
if [ '${NEXUS_DEPLOY_MODE}' = 'source' ]; then
  until sudo docker exec skillhub-postgres pg_isready -U skillhub -d postgres >/dev/null 2>&1; do
    sleep 2
  done
  if ! sudo docker exec skillhub-postgres psql -U skillhub -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname = 'nexus_source'\" | grep -q 1; then
    sudo docker exec skillhub-postgres psql -U skillhub -d postgres -c \"CREATE DATABASE nexus_source\"
  fi
  sudo docker compose \${compose_files} build --no-cache nexus
  sudo docker compose \${compose_files} build skillhub
  sudo docker compose \${compose_files} up -d --force-recreate
else
  sudo docker compose \${compose_files} up --build -d --force-recreate
fi
"
