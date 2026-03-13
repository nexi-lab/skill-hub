#!/usr/bin/env bash

set -euxo pipefail

exec > >(tee -a /var/log/skill-hub-startup.log) 2>&1

REPO_URL="${REPO_URL:-https://github.com/nexi-lab/skill-hub.git}"
REPO_REF="${REPO_REF:-main}"
APP_DIR="${APP_DIR:-/opt/skill-hub}"

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  gnupg

install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
fi
chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable
EOF

apt-get update
apt-get install -y --no-install-recommends \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

systemctl enable --now docker

mkdir -p /opt
if [ ! -d "${APP_DIR}/.git" ]; then
  git clone "${REPO_URL}" "${APP_DIR}"
fi

cd "${APP_DIR}"
git fetch origin
git checkout "${REPO_REF}"
git reset --hard "origin/${REPO_REF}"

if [ ! -f .env ]; then
  NEXUS_API_KEY="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48)"
  cat >.env <<EOF
NEXUS_API_KEY=${NEXUS_API_KEY}
NEXUS_VERSION=latest
EOF
fi

docker compose \
  -f compose.yaml \
  -f deploy/gcp/compose.gcp.yaml \
  up --build -d

for _ in $(seq 1 120); do
  if curl -fsS http://127.0.0.1:8040/health >/dev/null; then
    exit 0
  fi
  sleep 5
done

docker compose \
  -f compose.yaml \
  -f deploy/gcp/compose.gcp.yaml \
  ps -a

docker compose \
  -f compose.yaml \
  -f deploy/gcp/compose.gcp.yaml \
  logs --tail=200

exit 1
