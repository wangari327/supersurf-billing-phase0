#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${APP_ROOT:-/opt/supersurf-sandbox}"
SHARED_DIR="${APP_ROOT}/shared"
CURRENT_DIR="${APP_ROOT}/current"
RELEASES_DIR="${APP_ROOT}/releases"
BACKUPS_DIR="${APP_ROOT}/backups"
ENV_FILE="${SHARED_DIR}/sandbox.env"
PROJECT_NAME="${PROJECT_NAME:-supersurf-sandbox}"
PRIMARY_URL="https://sandbox.supersurf.co.ke"
API_URL="https://sandbox-api.supersurf.co.ke"

sudo_cmd() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

docker_cmd() {
  if docker ps >/dev/null 2>&1; then
    docker "$@"
  else
    sudo docker "$@"
  fi
}

deployment_revision() {
  if [ -n "${SUPERSURF_DEPLOYMENT_REVISION:-}" ]; then
    require_full_sha "${SUPERSURF_DEPLOYMENT_REVISION}"
    return
  fi
  if [ -f "${SHARED_DIR}/current-successful-sha" ]; then
    require_full_sha "$(tr -d '[:space:]' <"${SHARED_DIR}/current-successful-sha")"
    return
  fi
  printf '\n'
}

compose_cmd() {
  local revision
  revision="$(deployment_revision)"
  if docker ps >/dev/null 2>&1; then
    env \
      SUPERSURF_SANDBOX_ENV_FILE="${ENV_FILE}" \
      SUPERSURF_DEPLOYMENT_REVISION="${revision}" \
      docker compose -p "${PROJECT_NAME}" -f "${CURRENT_DIR}/compose.yml" "$@"
  else
    sudo env \
      SUPERSURF_SANDBOX_ENV_FILE="${ENV_FILE}" \
      SUPERSURF_DEPLOYMENT_REVISION="${revision}" \
      docker compose -p "${PROJECT_NAME}" -f "${CURRENT_DIR}/compose.yml" "$@"
  fi
}

require_full_sha() {
  local value="${1:-}"
  if [[ ! "${value}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "Deployment revision must be a full 40-character Git SHA." >&2
    exit 1
  fi
  printf '%s\n' "${value,,}"
}

ensure_env_file_secure() {
  if [ ! -f "${ENV_FILE}" ]; then
    echo "Missing environment file: ${ENV_FILE}" >&2
    exit 1
  fi
  local mode
  mode="$(stat -c '%a' "${ENV_FILE}")"
  if [ "${mode}" != "600" ]; then
    echo "Environment file ${ENV_FILE} must have mode 600, found ${mode}." >&2
    exit 1
  fi
}

wait_for_service_health() {
  local service="$1"
  local max_attempts="${2:-60}"
  local delay_seconds="${3:-5}"
  local attempt cid state
  for attempt in $(seq 1 "${max_attempts}"); do
    cid="$(compose_cmd ps -q "${service}" || true)"
    if [ -n "${cid}" ]; then
      state="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${cid}" 2>/dev/null || true)"
      if [ "${state}" = "healthy" ] || [ "${state}" = "running" ]; then
        echo "${service} is ${state}."
        return 0
      fi
      echo "Waiting for ${service}; current state: ${state:-unknown}."
    else
      echo "Waiting for ${service}; no container yet."
    fi
    sleep "${delay_seconds}"
  done
  echo "${service} did not become healthy in time." >&2
  compose_cmd ps || true
  compose_cmd logs --tail=80 "${service}" || true
  return 1
}

check_external_health() {
  local url="$1"
  local max_attempts="${2:-60}"
  local delay_seconds="${3:-10}"
  local attempt
  for attempt in $(seq 1 "${max_attempts}"); do
    if curl -fsS --max-time 10 "${url}" >/dev/null; then
      echo "Healthy: ${url}"
      return 0
    fi
    echo "Waiting for HTTPS health: ${url} (${attempt}/${max_attempts})"
    sleep "${delay_seconds}"
  done
  echo "HTTPS health check failed: ${url}" >&2
  compose_cmd ps || true
  compose_cmd logs --tail=120 caddy web || true
  return 1
}

check_all_external_health() {
  check_external_health "${PRIMARY_URL}/healthz/"
  check_external_health "${PRIMARY_URL}/readyz/"
  check_external_health "${API_URL}/healthz/"
}

check_port_available_or_sandbox() {
  local port="$1"
  local listeners
  listeners="$(sudo_cmd lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -z "${listeners}" ]; then
    return 0
  fi
  if docker_cmd ps --format '{{.Names}} {{.Ports}}' 2>/dev/null \
    | grep -E 'supersurf-sandbox.*caddy' \
    | grep -qE "0\.0\.0\.0:${port}->|:::${port}->"; then
    echo "Port ${port} is already held by the SuperSurf sandbox Caddy container."
    return 0
  fi
  echo "Port ${port} is occupied by an unrelated service:" >&2
  echo "${listeners}" >&2
  return 1
}
