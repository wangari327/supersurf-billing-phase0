#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/sandbox/common.sh
source "${SCRIPT_DIR}/common.sh"

echo "Current successful SHA: $(cat "${SHARED_DIR}/current-successful-sha" 2>/dev/null || echo none)"
echo "Previous successful SHA: $(cat "${SHARED_DIR}/previous-successful-sha" 2>/dev/null || echo none)"
if [ -f "${CURRENT_DIR}/compose.yml" ]; then
  compose_cmd ps || true
  echo
  echo "Container health:"
  for service in postgres broker web caddy; do
    cid="$(compose_cmd ps -q "${service}" 2>/dev/null || true)"
    if [ -n "${cid}" ]; then
      state="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${cid}" 2>/dev/null || true)"
      echo "  ${service}: ${state:-unknown}"
    else
      echo "  ${service}: missing"
    fi
  done
fi

echo
df -h "${APP_ROOT}" || true
echo
free -h || true
echo
swapon --show || true
echo
for url in "${PRIMARY_URL}/healthz/" "${PRIMARY_URL}/readyz/" "${API_URL}/healthz/"; do
  if curl -fsS --max-time 10 "${url}" >/dev/null; then
    echo "HTTPS ok: ${url}"
  else
    echo "HTTPS failed: ${url}"
  fi
done
