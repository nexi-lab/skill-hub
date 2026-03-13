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
