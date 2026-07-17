#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/sandbox/common.sh
source "${SCRIPT_DIR}/common.sh"

umask 077
mkdir -p "${SHARED_DIR}"

read_env_value() {
  local key="$1"
  if [ ! -f "${ENV_FILE}" ]; then
    return 0
  fi
  grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- || true
}

secret_key="$(read_env_value DJANGO_SECRET_KEY)"
postgres_password="$(read_env_value POSTGRES_PASSWORD)"
mpesa_callback_token="$(read_env_value MPESA_CALLBACK_TOKEN)"
mpesa_paybill_ingestion_enabled="$(read_env_value MPESA_PAYBILL_INGESTION_ENABLED)"
mpesa_paybill_external_identifier="$(read_env_value MPESA_PAYBILL_EXTERNAL_IDENTIFIER)"

if [ -z "${secret_key}" ]; then
  secret_key="$(openssl rand -base64 48 | tr '+/' '-_' | tr -d '=')"
fi
if [ -z "${postgres_password}" ]; then
  postgres_password="$(openssl rand -hex 32)"
fi
if [ -z "${mpesa_callback_token}" ]; then
  mpesa_callback_token="$(openssl rand -hex 32)"
fi
if [ -z "${mpesa_paybill_ingestion_enabled}" ]; then
  mpesa_paybill_ingestion_enabled="false"
fi

tmp_file="$(mktemp)"
cat >"${tmp_file}" <<EOF
SUPERSURF_ENVIRONMENT=LAB
SUPERSURF_PUBLIC_DEPLOYMENT=true
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=${secret_key}
DJANGO_ALLOWED_HOSTS=sandbox.supersurf.co.ke,sandbox-api.supersurf.co.ke
DJANGO_CSRF_TRUSTED_ORIGINS=https://sandbox.supersurf.co.ke,https://sandbox-api.supersurf.co.ke
DATABASE_URL=postgresql://supersurf:${postgres_password}@postgres:5432/supersurf
POSTGRES_DB=supersurf
POSTGRES_USER=supersurf
POSTGRES_PASSWORD=${postgres_password}
MPESA_CALLBACK_TOKEN=${mpesa_callback_token}
MPESA_PAYBILL_INGESTION_ENABLED=${mpesa_paybill_ingestion_enabled}
MPESA_PAYBILL_EXTERNAL_IDENTIFIER=${mpesa_paybill_external_identifier}
BROKER_URL=redis://broker:6379/0
CELERY_RESULT_BACKEND=redis://broker:6379/0
SECURE_HSTS_SECONDS=0
EOF
chmod 600 "${tmp_file}"
mv "${tmp_file}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

grep -qx 'SUPERSURF_ENVIRONMENT=LAB' "${ENV_FILE}"
grep -qx 'SUPERSURF_PUBLIC_DEPLOYMENT=true' "${ENV_FILE}"
grep -qx 'DJANGO_DEBUG=false' "${ENV_FILE}"
grep -qx 'DJANGO_ALLOWED_HOSTS=sandbox.supersurf.co.ke,sandbox-api.supersurf.co.ke' "${ENV_FILE}"
grep -qx 'DJANGO_CSRF_TRUSTED_ORIGINS=https://sandbox.supersurf.co.ke,https://sandbox-api.supersurf.co.ke' "${ENV_FILE}"
grep -q '^MPESA_CALLBACK_TOKEN=' "${ENV_FILE}"
grep -q '^MPESA_PAYBILL_INGESTION_ENABLED=' "${ENV_FILE}"
grep -q '^MPESA_PAYBILL_EXTERNAL_IDENTIFIER=' "${ENV_FILE}"
grep -qx 'BROKER_URL=redis://broker:6379/0' "${ENV_FILE}"
grep -qx 'CELERY_RESULT_BACKEND=redis://broker:6379/0' "${ENV_FILE}"
grep -qx 'SECURE_HSTS_SECONDS=0' "${ENV_FILE}"

echo "Sandbox environment file is present with secure permissions."
echo "Required non-secret sandbox settings validated."
