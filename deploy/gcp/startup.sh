#!/usr/bin/env bash

set -euxo pipefail

exec > >(tee -a /var/log/skill-hub-startup.log) 2>&1

APP_DIR="${APP_DIR:-/opt/skill-hub}"

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
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

mkdir -p "${APP_DIR}"
chmod 755 /opt "${APP_DIR}"

exit 0
