#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/sandbox/common.sh
source "${SCRIPT_DIR}/common.sh"

follow=0
tail_lines=200
services=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    -f|--follow)
      follow=1
      shift
      ;;
    --tail)
      tail_lines="${2:-200}"
      shift 2
      ;;
    web|postgres|broker|caddy)
      services+=("$1")
      shift
      ;;
    *)
      echo "Usage: $0 [--tail LINES] [--follow] [web|postgres|broker|caddy ...]" >&2
      exit 1
      ;;
  esac
done

echo "Showing recent container logs. Application logs must not contain credentials or payment secrets."
args=(logs "--tail=${tail_lines}")
if [ "${follow}" -eq 1 ]; then
  args+=(--follow)
fi
if [ "${#services[@]}" -gt 0 ]; then
  args+=("${services[@]}")
fi
compose_cmd "${args[@]}"
