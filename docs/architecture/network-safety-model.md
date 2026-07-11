# Network Safety Model

## Safety Principles

- Financial truth must be recorded before any network action.
- Network actions must be asynchronous, audited, retryable, and visible.
- Production defaults to dry-run.
- Router writes must be allowlisted.
- Never automatically touch live SuperSurf L009 during Phase 0.
- Never execute generated migration scripts automatically.

## Protected Router Areas

The system must not modify:

- WAN configuration
- Routing
- CAKE or queue strategy outside explicitly reviewed subscriber plan attributes
- WireGuard
- Watchdog settings
- Backup settings
- Firewall rules not directly approved for the subscriber workflow
- System packages
- Router identity
- Time settings

## Allowed Future Actions

After reviewed implementation and lab validation:

- Read router health
- Read active PPPoE sessions
- Disconnect a subscriber session
- Apply CoA or disconnect requests where supported
- Verify NAS reachability
- Retry provisioning jobs

## Dry-Run Mode

Dry-run mode must:

- Be enabled by default
- Record intended commands
- Avoid changing RouterOS or FreeRADIUS state
- Be visible in UI and audit events
- Block production activation until Owner explicitly disables it for a configured integration

## Lab Migration Plan

Later phases must test on CHR or a spare-router lab before production:

- One test subscriber
- One test CPE
- RADIUS authentication
- RADIUS accounting
- Plan rate limits
- Session visibility
- Disconnection
- Reconnection
- Payment activation
- Suspension
- Reactivation
- Failure rollback
- Staged migration
- Customer credentials
- CPE configuration
- Support procedures

