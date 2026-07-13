#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/sandbox/common.sh
source "${SCRIPT_DIR}/common.sh"

if [ "$(id -u)" -eq 0 ]; then
  DEPLOY_USER="${SUDO_USER:-github-runner}"
else
  DEPLOY_USER="$(id -un)"
fi
DEPLOY_GROUP="$(id -gn "${DEPLOY_USER}")"

if [ ! -r /etc/os-release ]; then
  echo "Cannot determine operating system." >&2
  exit 1
fi
# shellcheck disable=SC1091
. /etc/os-release
if [ "${ID:-}" != "ubuntu" ] || [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "This bootstrap supports Ubuntu 24.04; found ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi

sudo_cmd apt-get update
sudo_cmd apt-get install -y ca-certificates curl dnsutils gnupg lsb-release lsof openssl

install_docker_repository() {
  sudo_cmd install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | sudo_cmd gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo_cmd chmod a+r /etc/apt/keyrings/docker.gpg
  fi
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    | sudo_cmd tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo_cmd apt-get update
}

if ! command -v docker >/dev/null 2>&1; then
  install_docker_repository
  sudo_cmd apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
elif ! docker compose version >/dev/null 2>&1 && ! sudo docker compose version >/dev/null 2>&1; then
  install_docker_repository
  sudo_cmd apt-get install -y docker-compose-plugin
fi

sudo_cmd systemctl enable --now docker
sudo_cmd usermod -aG docker "${DEPLOY_USER}"

sudo_cmd install -d -m 0750 -o "${DEPLOY_USER}" -g "${DEPLOY_GROUP}" "${APP_ROOT}"
sudo_cmd install -d -m 0750 -o "${DEPLOY_USER}" -g "${DEPLOY_GROUP}" "${SHARED_DIR}"
sudo_cmd install -d -m 0750 -o "${DEPLOY_USER}" -g "${DEPLOY_GROUP}" "${CURRENT_DIR}"
sudo_cmd install -d -m 0750 -o "${DEPLOY_USER}" -g "${DEPLOY_GROUP}" "${RELEASES_DIR}"
sudo_cmd install -d -m 0750 -o "${DEPLOY_USER}" -g "${DEPLOY_GROUP}" "${BACKUPS_DIR}"

if ! swapon --show --noheadings | grep -q .; then
  if [ ! -f /swapfile ]; then
    sudo_cmd fallocate -l 2G /swapfile
    sudo_cmd chmod 600 /swapfile
    sudo_cmd mkswap /swapfile
  fi
  sudo_cmd swapon /swapfile || true
fi
if ! grep -Eq '^[^#[:space:]]+[[:space:]]+none[[:space:]]+swap[[:space:]]' /etc/fstab; then
  echo "/swapfile none swap sw 0 0" | sudo_cmd tee -a /etc/fstab >/dev/null
fi

check_port_available_or_sandbox 80
check_port_available_or_sandbox 443

docker_cmd --version
docker_cmd compose version
echo "Sandbox bootstrap complete for ${DEPLOY_USER}."
