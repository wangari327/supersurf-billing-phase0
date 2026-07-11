# Backup Design

## Backup Scope

Backups must include:

- PostgreSQL database
- Uploaded M-PESA statements
- Receipt assets
- Organization branding assets
- Configuration excluding externally stored secrets
- Encryption-key recovery instructions

## Exclusions

Do not include plaintext production secrets in ordinary backups. If secrets are stored in an external secret manager, back up references and recovery procedures, not secret material.

## MVP Backup Plan

- Automated daily PostgreSQL backups
- Configurable retention settings
- Encrypted local backup artifact
- Documented off-site copy procedure
- Restore script
- Restore test into a clean environment
- Backup status visible in operator dashboard
- Audit events for backup and restore actions

## Restore Requirements

The restore guide must cover:

- Fresh host preparation
- Database restore
- Uploaded assets restore
- Secret reconfiguration
- Integrity checks
- Staff login verification
- Payment idempotency verification
- Dry-run network verification

