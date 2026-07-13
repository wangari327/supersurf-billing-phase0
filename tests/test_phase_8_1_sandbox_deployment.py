from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CADDYFILE_0644_INSTALL = 'install -m 0644 "${SCRIPT_DIR}/Caddyfile" "${CURRENT_DIR}/Caddyfile"'
CADDYFILE_0640_INSTALL = 'install -m 0640 "${SCRIPT_DIR}/Caddyfile" "${CURRENT_DIR}/Caddyfile"'
COMPOSE_0640_INSTALL = 'install -m 0640 "${SCRIPT_DIR}/compose.yml" "${CURRENT_DIR}/compose.yml"'
HELPER_0750_INSTALL = 'install -m 0750 "${SCRIPT_DIR}/${helper}" "${CURRENT_DIR}/${helper}"'


def test_sandbox_deploy_installs_caddyfile_world_readable_but_not_writable():
    deploy_script = (REPO_ROOT / "deploy" / "sandbox" / "deploy.sh").read_text()

    assert CADDYFILE_0644_INSTALL in deploy_script
    assert CADDYFILE_0640_INSTALL not in deploy_script
    assert COMPOSE_0640_INSTALL in deploy_script
    assert HELPER_0750_INSTALL in deploy_script


def test_sandbox_caddy_validation_uses_actual_read_only_compose_mount_before_start():
    deploy_script = (REPO_ROOT / "deploy" / "sandbox" / "deploy.sh").read_text()
    compose_file = (REPO_ROOT / "deploy" / "sandbox" / "compose.yml").read_text()

    assert "./Caddyfile:/etc/caddy/Caddyfile:ro" in compose_file
    assert 'mode="$(stat -c \'%a\' "${caddyfile}")"' in deploy_script
    assert 'if [ "${mode}" != "644" ]; then' in deploy_script
    assert "appears to contain secret material" in deploy_script
    assert "compose_cmd run --rm --no-deps caddy" in deploy_script
    assert "validate" in deploy_script
    assert "--config /etc/caddy/Caddyfile" in deploy_script
    assert "--adapter caddyfile" in deploy_script
    validation_call = deploy_script.index("\nvalidate_caddyfile\n")
    assert validation_call < deploy_script.index("compose_cmd up -d caddy")
