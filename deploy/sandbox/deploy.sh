#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=deploy/sandbox/common.sh
source "${SCRIPT_DIR}/common.sh"

DEPLOY_SHA="$(require_full_sha "${SUPERSURF_DEPLOYMENT_REVISION:-${GITHUB_SHA:-}}")"
export SUPERSURF_DEPLOYMENT_REVISION="${DEPLOY_SHA}"

required_files=(compose.yml Caddyfile common.sh rollback.sh create-owner.sh status.sh logs.sh)
for file in "${required_files[@]}"; do
  if [ ! -f "${SCRIPT_DIR}/${file}" ]; then
    echo "Missing deployment file: ${SCRIPT_DIR}/${file}" >&2
    exit 1
  fi
done
ensure_env_file_secure
check_port_available_or_sandbox 80
check_port_available_or_sandbox 443

check_domain_dns() {
  local domain="$1"
  local public_ip
  public_ip="$(curl -fsS --max-time 10 https://api.ipify.org)"
  mapfile -t records < <(dig +short A "${domain}" | grep -E '^[0-9.]+$' || true)
  if [ "${#records[@]}" -eq 0 ]; then
    echo "DNS for ${domain} has no A record." >&2
    exit 1
  fi
  for record in "${records[@]}"; do
    if [ "${record}" = "${public_ip}" ]; then
      echo "DNS ok for ${domain}: ${record}"
      return 0
    fi
  done
  echo "DNS for ${domain} does not point to this VPS public IP (${public_ip})." >&2
  printf 'Resolved A records: %s\n' "${records[*]}" >&2
  exit 1
}

check_domain_dns sandbox.supersurf.co.ke
check_domain_dns sandbox-api.supersurf.co.ke

install -m 0640 "${SCRIPT_DIR}/compose.yml" "${CURRENT_DIR}/compose.yml"
install -m 0644 "${SCRIPT_DIR}/Caddyfile" "${CURRENT_DIR}/Caddyfile"
for helper in common.sh rollback.sh create-owner.sh status.sh logs.sh; do
  install -m 0750 "${SCRIPT_DIR}/${helper}" "${CURRENT_DIR}/${helper}"
done

validate_caddyfile() {
  local caddyfile="${CURRENT_DIR}/Caddyfile"
  if [ ! -f "${caddyfile}" ]; then
    echo "Missing deployed Caddyfile: ${caddyfile}" >&2
    exit 1
  fi
  local mode
  mode="$(stat -c '%a' "${caddyfile}")"
  if [ "${mode}" != "644" ]; then
    echo "Deployed Caddyfile must have mode 644, found ${mode}." >&2
    exit 1
  fi
  if grep -Eiq '(secret|password|token|credential|consumer[_-]?key|consumer[_-]?secret|passkey|authorization)' "${caddyfile}"; then
    echo "Deployed Caddyfile appears to contain secret material." >&2
    exit 1
  fi
  compose_cmd run --rm --no-deps caddy \
    caddy validate \
    --config /etc/caddy/Caddyfile \
    --adapter caddyfile
}

validate_caddyfile

echo "Building supersurf-billing:${DEPLOY_SHA}"
docker_cmd build --pull --tag "supersurf-billing:${DEPLOY_SHA}" "${REPO_ROOT}"
printf '%s\n' "${DEPLOY_SHA}" >"${SHARED_DIR}/intended-sha"

compose_cmd up -d postgres broker
wait_for_service_health postgres 60 5
wait_for_service_health broker 60 5

compose_cmd run --rm --no-deps web python manage.py migrate --noinput
compose_cmd run --rm --no-deps web python manage.py seed_roles
compose_cmd run --rm --no-deps web python manage.py sync_mpesa_paybill_profile

compose_cmd up -d web
wait_for_service_health web 60 5

compose_cmd up -d caddy
wait_for_service_health web 60 5
check_all_external_health

current_successful_file="${SHARED_DIR}/current-successful-sha"
previous_successful_file="${SHARED_DIR}/previous-successful-sha"
if [ -f "${current_successful_file}" ]; then
  current_successful="$(cat "${current_successful_file}")"
  if [ "${current_successful}" != "${DEPLOY_SHA}" ]; then
    printf '%s\n' "${current_successful}" >"${previous_successful_file}"
  fi
fi
printf '%s\n' "${DEPLOY_SHA}" >"${current_successful_file}"

previous_successful=""
if [ -f "${previous_successful_file}" ]; then
  previous_successful="$(cat "${previous_successful_file}")"
fi
docker_cmd images --format '{{.Repository}}:{{.Tag}}' supersurf-billing \
  | while read -r image; do
      tag="${image#supersurf-billing:}"
      if [ "${tag}" != "${DEPLOY_SHA}" ] && [ "${tag}" != "${previous_successful}" ]; then
        docker_cmd image rm "${image}" >/dev/null || true
      fi
    done

compose_cmd ps
echo "Deployed revision: ${DEPLOY_SHA}"
echo "Primary URL: ${PRIMARY_URL}/"
echo "API URL: ${API_URL}/"
