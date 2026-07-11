# ADR 0003: Persist Financial Truth Before Network Actions

## Status

Proposed for Phase 1 and binding for payment phases.

## Context

M-PESA callbacks and subscriber renewals must remain correct even when RouterOS, FreeRADIUS, or workers are unavailable.

## Decision

Persist payment events and append ledger entries transactionally before enqueueing provisioning or network actions.

Network actions are separate audited jobs that can retry safely.

## Consequences

Positive:

- RouterOS downtime cannot lose a payment.
- RADIUS downtime cannot lose a payment.
- Duplicate callbacks can be handled with database constraints and transactional locks.
- Reconciliation remains possible.

Tradeoffs:

- Subscriber service state may briefly lag financial state.
- UI must clearly show pending provisioning jobs.

## Rejected Alternatives

- Apply network changes directly in webhook request cycle.
- Treat RouterOS or FreeRADIUS as the source of truth for billing.

