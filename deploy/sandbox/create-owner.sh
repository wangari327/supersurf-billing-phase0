#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/sandbox/common.sh
source "${SCRIPT_DIR}/common.sh"

username=""
email=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --username)
      username="${2:-}"
      shift 2
      ;;
    --email)
      email="${2:-}"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--username USERNAME] [--email EMAIL]" >&2
      exit 1
      ;;
  esac
done

if [ -z "${username}" ]; then
  read -r -p "Owner username: " username
fi
if [ -z "${email}" ]; then
  read -r -p "Owner email (optional): " email
fi

if [ -z "${username}" ]; then
  echo "Owner username is required." >&2
  exit 1
fi

ensure_env_file_secure
echo "This command is intended for an interactive SSH session, not the deployment workflow."
echo "The password will be requested by Django and will not be accepted as a command-line argument."
compose_cmd run --rm web python manage.py create_first_owner \
  --username "${username}" \
  --email "${email}"
