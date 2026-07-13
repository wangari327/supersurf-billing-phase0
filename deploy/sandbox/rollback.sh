#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/sandbox/common.sh
source "${SCRIPT_DIR}/common.sh"

previous_file="${SHARED_DIR}/previous-successful-sha"
current_file="${SHARED_DIR}/current-successful-sha"
if [ ! -f "${previous_file}" ]; then
  echo "No previous successful revision is recorded. Cannot guess a rollback target." >&2
  exit 1
fi

ROLLBACK_SHA="$(require_full_sha "$(cat "${previous_file}")")"
export SUPERSURF_DEPLOYMENT_REVISION="${ROLLBACK_SHA}"
ensure_env_file_secure

echo "Rolling back application image to ${ROLLBACK_SHA}."
echo "Database migrations are not rolled back. Forward-only schema changes may be incompatible."
if ! docker_cmd image inspect "supersurf-billing:${ROLLBACK_SHA}" >/dev/null 2>&1; then
  echo "Required rollback image supersurf-billing:${ROLLBACK_SHA} is not present." >&2
  exit 1
fi

compose_cmd up -d web caddy
wait_for_service_health web 60 5
check_all_external_health

old_current=""
if [ -f "${current_file}" ]; then
  old_current="$(cat "${current_file}")"
fi
if [ -n "${old_current}" ] && [ "${old_current}" != "${ROLLBACK_SHA}" ]; then
  printf '%s\n' "${old_current}" >"${previous_file}"
fi
printf '%s\n' "${ROLLBACK_SHA}" >"${current_file}"

compose_cmd ps
echo "Rollback complete: ${ROLLBACK_SHA}"
