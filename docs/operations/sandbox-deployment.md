# Sandbox Deployment

This document describes the SuperSurf sandbox deployment foundation. It is sandbox infrastructure, not production infrastructure. Phase 9 adds inbound Daraja sandbox callback evidence capture only. It does not create canonical payments, Wallet credits, billing periods, renewals, invoices, receipts, network access, or production Daraja integrations. No production payment credentials should be stored here.

## Purpose And Scope

The sandbox publishes the existing Phase 8 Django application at:

- `https://sandbox.supersurf.co.ke/`
- `https://sandbox-api.supersurf.co.ke/`

Both hostnames reverse proxy to the same Django web service. The second hostname is used for Daraja sandbox callback evidence endpoints. Phase 9 does not add outbound STK Push, STK Query, canonical payment creation, invoices, receipts, automatic renewals, network provisioning, or customer portals.

## Architecture

GitHub Actions runs a manual deployment workflow. The first job verifies the repository on `ubuntu-latest` with PostgreSQL. The second job runs only on the self-hosted runner labelled `self-hosted`, `Linux`, `X64`, and `supersurf-sandbox`.

The VPS stack uses Docker Compose with:

- `web`: the Django application image tagged as `supersurf-billing:<full-commit-sha>`
- `postgres`: PostgreSQL 17 Alpine, private to the Compose network
- `broker`: Valkey 8 Alpine, private to the Compose network
- `caddy`: Caddy 2 Alpine, the only service publishing ports `80` and `443`

The Django application port, PostgreSQL port, and Valkey port are not published on the host. Caddy obtains and renews HTTPS certificates for both sandbox hostnames.

## Manual Workflow Execution

The deploy workflow is manual only and is not triggered by pushes or pull requests.

1. Open GitHub.
2. Go to `wangari327/supersurf-billing-phase0`.
3. Select **Actions**.
4. Select **Deploy Sandbox**.
5. Select **Run workflow** on `main`.

Do not dispatch the workflow from a pull request or fork. The self-hosted runner must only run trusted `main` code.

## Initial Deployment Sequence

The workflow performs these steps:

1. Verify Python, Django, CSS, migrations, tests, linting, type checks, secret scans, dependency audits, shell syntax, and sandbox Compose configuration.
2. Run `deploy/sandbox/bootstrap.sh` on the VPS.
3. Run `deploy/sandbox/prepare-environment.sh` on the VPS.
4. Run `deploy/sandbox/deploy.sh` with `SUPERSURF_DEPLOYMENT_REVISION` set to the full Git commit SHA.
5. Display non-secret status and health output.

The workflow does not create the first Owner account.

## Docker Bootstrap

`bootstrap.sh` supports Ubuntu 24.04. It installs basic deployment packages, installs Docker Engine and the Docker Compose plugin from Docker's official apt repository when Docker is absent, installs the Compose plugin from the same repository when only the plugin is missing, starts and enables Docker, and adds the runner user to the Docker group.

The current workflow run still uses `sudo docker` when needed, so deployment does not require logging out and back in after group membership changes.

The script does not modify SSH configuration, disable accounts, replace firewall rules, or close existing ports. It fails if ports `80` or `443` are occupied by an unrelated service. An existing SuperSurf sandbox Caddy container is accepted on later runs.

## Persistent Paths

The bootstrap creates:

- `/opt/supersurf-sandbox`
- `/opt/supersurf-sandbox/shared`
- `/opt/supersurf-sandbox/current`
- `/opt/supersurf-sandbox/releases`
- `/opt/supersurf-sandbox/backups`

The environment file is:

```text
/opt/supersurf-sandbox/shared/sandbox.env
```

It is generated only on the VPS, has mode `600`, is not committed to Git, and is not printed by the workflow.

## Persistent Docker Volumes

The sandbox Compose project uses named volumes for:

- PostgreSQL data
- Caddy certificate and runtime data
- Caddy configuration state

Deployment and rollback scripts never delete these volumes.

## Environment

The generated environment uses:

```text
SUPERSURF_ENVIRONMENT=LAB
SUPERSURF_PUBLIC_DEPLOYMENT=true
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=sandbox.supersurf.co.ke,sandbox-api.supersurf.co.ke
DJANGO_CSRF_TRUSTED_ORIGINS=https://sandbox.supersurf.co.ke,https://sandbox-api.supersurf.co.ke
SECURE_HSTS_SECONDS=0
```

`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, and `MPESA_CALLBACK_TOKEN` are generated cryptographically on the VPS when absent and preserved across later deployments. `MPESA_CALLBACK_TOKEN` is generated with `openssl rand -hex 32`; it is required for public LAB deployments, must be at least 32 characters, and must never be printed by deployment or CI output.

Do not add Daraja credentials, M-PESA credentials, consumer keys, consumer secrets, passkeys, Paybill numbers, sandbox tokens, or fake production credentials. The callback token is a path secret stored only in the VPS `sandbox.env`; it is not a Daraja credential and must still be treated as secret.

## Public LAB Security

The visible environment banner remains `LAB`. Because `SUPERSURF_PUBLIC_DEPLOYMENT=true`, Django still requires public-deployment settings and enables secure cookies, SSL redirect, and `SECURE_PROXY_SSL_HEADER`.

Public LAB does not enable HSTS preload or includeSubDomains. HSTS duration defaults to `0` and can be raised later through `SECURE_HSTS_SECONDS` after certificate and Cloudflare behavior are reviewed.

## DNS And Cloudflare

Both DNS records must point to the VPS before deployment:

- `sandbox.supersurf.co.ke`
- `sandbox-api.supersurf.co.ke`

During the initial Caddy certificate bootstrap, Cloudflare records must be DNS-only. After certificates are issued and health checks pass, proxying can be reviewed separately. Ports `80` and `443` must be reachable publicly for Caddy certificate issuance and HTTPS traffic.

## Viewing The Application

After deployment, open:

```text
https://sandbox.supersurf.co.ke/
```

The future API hostname should also reach the same Django application:

```text
https://sandbox-api.supersurf.co.ke/
```

Health URLs:

- `https://sandbox.supersurf.co.ke/healthz/`
- `https://sandbox.supersurf.co.ke/readyz/`
- `https://sandbox-api.supersurf.co.ke/healthz/`

## Create The First Owner

Run this manually over SSH, not through the non-interactive deployment workflow:

```bash
/opt/supersurf-sandbox/current/create-owner.sh --username owner --email ""
```

The script runs Django's existing `create_first_owner` command. It never accepts a password as a command-line argument. The password prompt is handled by Django.

## Status And Logs

Status:

```bash
/opt/supersurf-sandbox/current/status.sh
```

Recent logs:

```bash
/opt/supersurf-sandbox/current/logs.sh
```

Follow web logs explicitly:

```bash
/opt/supersurf-sandbox/current/logs.sh --follow web
```

Application logs must not contain credentials, tokens, payment secrets, request bodies, or environment-file contents.

## Daraja Sandbox Callback Evidence

Phase 9 exposes three unauthenticated-by-session callback routes on the API hostname. Daraja callbacks cannot be assumed to carry a custom authentication header, so each route uses an unguessable token path segment:

```text
https://sandbox-api.supersurf.co.ke/api/payment-callbacks/<token>/c2b/validation/
https://sandbox-api.supersurf.co.ke/api/payment-callbacks/<token>/c2b/confirmation/
https://sandbox-api.supersurf.co.ke/api/payment-callbacks/<token>/stk/callback/
```

The endpoints accept JSON `POST` requests only, reject malformed JSON with HTTP 400, reject oversized bodies above 64 KiB with HTTP 413, and return HTTP 404 for missing or incorrect tokens. Accepted C2B validation, C2B confirmation, and STK result callbacks return JSON:

```json
{"ResultCode": 0, "ResultDesc": "Accepted"}
```

Repeated callbacks are deduplicated by event type plus the stable provider identifier where present, or by event type plus canonical payload digest as a fallback. Duplicates receive the same successful acknowledgement and do not update the original evidence row.

To print the three full callback URLs during an authenticated SSH operator session, run:

```bash
cd /opt/supersurf-sandbox/current
export SUPERSURF_DEPLOYMENT_REVISION="$(cat /opt/supersurf-sandbox/shared/current-successful-sha)"
export SUPERSURF_SANDBOX_ENV_FILE="/opt/supersurf-sandbox/shared/sandbox.env"
sudo env \
  SUPERSURF_DEPLOYMENT_REVISION="$SUPERSURF_DEPLOYMENT_REVISION" \
  SUPERSURF_SANDBOX_ENV_FILE="$SUPERSURF_SANDBOX_ENV_FILE" \
  docker compose -p supersurf-sandbox -f compose.yml run --rm web \
  python manage.py show_mpesa_callback_urls
```

Do not paste the printed URLs into GitHub issues, normal logs, screenshots, support tickets, or chat channels because the token is embedded in the path.

On 2026-07-17, the Daraja 3.0 sandbox C2B Register URL form rejected the attempted validation URL because it contained the word "MPESA". The portal displayed provider-neutral HTTPS confirmation and validation examples, so the public routes now use the neutral `/api/payment-callbacks/` prefix. This is a URL compatibility correction only.

The provider-neutral routes were manually deployed. Daraja C2B Register URL then returned `ResponseCode` `00000000` and `ResponseDescription` `Success`. A controlled Paybill simulation using `CustomerPayBillOnline`, amount `1`, and synthetic `BillRefNumber` `SS000001` produced both validation and confirmation callbacks. The events preserved the same provider transaction identifier, account reference, and amount while using independent event-type-specific idempotency keys. Sensitive name, telephone, and balance fields were redacted, and the observed C2B payloads contained no result code.

A controlled M-Pesa Express/STK Push simulator request using amount `1`, `CustomerPayBillOnline`, and synthetic `AccountReference` `SS000001` was accepted with `ResponseCode` `0`. The corresponding `stk_result` callback carried matching request identifiers and reported `ResultCode` `1037` with `ResultDesc` `No response from user.` The callback contained no metadata, so no amount, provider transaction identifier, or account reference was available in the stored event. This is an observed provider payload characteristic, not an application failure. All actual sandbox shortcode, MSISDN, request identifier, and callback identifier values are intentionally omitted.

Captured events are visible to operators with `billing.view_mpesacallbackevent` at:

```text
https://sandbox.supersurf.co.ke/mpesa-callbacks/
```

The list and detail pages display only the event envelope, extracted safe fields, and sanitized payload JSON. The reviewed pages did not display the callback token, callback URL, raw request body, request headers, cookies, client IP address, session data, credentials, or unredacted telephone, name, or balance fields.

This evidence proves callback registration, delivery, and safe evidence capture only. The evidence capture phase intentionally does not interpret a successful acknowledgement or provider response as payment, does not create `Payment` records, does not credit Wallets or mutate the ledger, does not create `BillingPeriod` or `BillingCharge` records, does not activate or renew services, does not reconcile transactions, and does not establish production readiness. Callback payloads should be inspected through the operator UI and must never be pasted into normal application logs.

## Revision Tracking

Deployment records:

- `/opt/supersurf-sandbox/shared/intended-sha`
- `/opt/supersurf-sandbox/shared/current-successful-sha`
- `/opt/supersurf-sandbox/shared/previous-successful-sha`

A new revision is marked successful only after internal container health and external HTTPS checks pass.

## Rollback

Rollback uses the recorded previous successful application image SHA:

```bash
/opt/supersurf-sandbox/current/rollback.sh
```

Rollback never guesses a revision, never deletes persistent volumes, and does not destructively roll back database migrations. Application rollback may be incompatible after forward-only schema changes.

## Backups

Create a timestamped backup without exposing the PostgreSQL password in host process arguments or shell history:

```bash
cd /opt/supersurf-sandbox/current
export SUPERSURF_DEPLOYMENT_REVISION="$(cat /opt/supersurf-sandbox/shared/current-successful-sha)"
export SUPERSURF_SANDBOX_ENV_FILE="/opt/supersurf-sandbox/shared/sandbox.env"
backup="/opt/supersurf-sandbox/backups/supersurf-$(date -u +%Y%m%dT%H%M%SZ).dump"
sudo env \
  SUPERSURF_DEPLOYMENT_REVISION="$SUPERSURF_DEPLOYMENT_REVISION" \
  SUPERSURF_SANDBOX_ENV_FILE="$SUPERSURF_SANDBOX_ENV_FILE" \
  docker compose -p supersurf-sandbox -f compose.yml exec -T postgres \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "$backup"
chmod 600 "$backup"
```

Verify a backup:

```bash
pg_restore --list "$backup" >/dev/null
```

Restore procedure for a planned sandbox restore window:

```bash
cd /opt/supersurf-sandbox/current
export SUPERSURF_DEPLOYMENT_REVISION="$(cat /opt/supersurf-sandbox/shared/current-successful-sha)"
export SUPERSURF_SANDBOX_ENV_FILE="/opt/supersurf-sandbox/shared/sandbox.env"
sudo env \
  SUPERSURF_DEPLOYMENT_REVISION="$SUPERSURF_DEPLOYMENT_REVISION" \
  SUPERSURF_SANDBOX_ENV_FILE="$SUPERSURF_SANDBOX_ENV_FILE" \
  docker compose -p supersurf-sandbox -f compose.yml stop web
cat "$backup" | sudo env \
  SUPERSURF_DEPLOYMENT_REVISION="$SUPERSURF_DEPLOYMENT_REVISION" \
  SUPERSURF_SANDBOX_ENV_FILE="$SUPERSURF_SANDBOX_ENV_FILE" \
  docker compose -p supersurf-sandbox -f compose.yml exec -T postgres \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner -'
sudo env \
  SUPERSURF_DEPLOYMENT_REVISION="$SUPERSURF_DEPLOYMENT_REVISION" \
  SUPERSURF_SANDBOX_ENV_FILE="$SUPERSURF_SANDBOX_ENV_FILE" \
  docker compose -p supersurf-sandbox -f compose.yml up -d web caddy
/opt/supersurf-sandbox/current/status.sh
```

Test restores should be performed on a separate VPS or separate database before relying on a backup.

## Moving To Another VPS

1. Provision Ubuntu 24.04.
2. Install and start the self-hosted GitHub Actions runner with the `supersurf-sandbox` label.
3. Move backup files securely to the new VPS.
4. Update Cloudflare DNS records to the new VPS IP and keep them DNS-only for certificate bootstrap.
5. Run the manual GitHub deployment workflow.
6. Restore the selected PostgreSQL backup if needed.
7. Run status and HTTPS health checks.

## 1 GB VPS Limits

The stack is intentionally small: one Gunicorn worker with threads, PostgreSQL, Valkey, and Caddy. A 2 GB swapfile is created only when no usable swap exists. This sandbox is not sized for production traffic, background workers, scheduler workloads, or large imports.

## Stop, Start, And Redeploy

Stop:

```bash
cd /opt/supersurf-sandbox/current
export SUPERSURF_DEPLOYMENT_REVISION="$(cat /opt/supersurf-sandbox/shared/current-successful-sha)"
export SUPERSURF_SANDBOX_ENV_FILE="/opt/supersurf-sandbox/shared/sandbox.env"
sudo env \
  SUPERSURF_DEPLOYMENT_REVISION="$SUPERSURF_DEPLOYMENT_REVISION" \
  SUPERSURF_SANDBOX_ENV_FILE="$SUPERSURF_SANDBOX_ENV_FILE" \
  docker compose -p supersurf-sandbox -f compose.yml stop
```

Start:

```bash
cd /opt/supersurf-sandbox/current
export SUPERSURF_DEPLOYMENT_REVISION="$(cat /opt/supersurf-sandbox/shared/current-successful-sha)"
export SUPERSURF_SANDBOX_ENV_FILE="/opt/supersurf-sandbox/shared/sandbox.env"
sudo env \
  SUPERSURF_DEPLOYMENT_REVISION="$SUPERSURF_DEPLOYMENT_REVISION" \
  SUPERSURF_SANDBOX_ENV_FILE="$SUPERSURF_SANDBOX_ENV_FILE" \
  docker compose -p supersurf-sandbox -f compose.yml up -d
```

Redeploy the same revision by manually running the GitHub workflow again from the same commit.

## Safe Removal

To remove the running sandbox while preserving backups, stop containers first and archive `/opt/supersurf-sandbox/backups`. Do not run `docker system prune` or `docker volume prune` unless the PostgreSQL and Caddy volumes have been intentionally backed up and the owner has approved deletion.
