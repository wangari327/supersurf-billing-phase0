# ADR 0001: Use Django Modular Monolith

## Status

Proposed for Phase 1.

## Context

SuperSurf Billing is initially for one owner-operated Kenyan ISP. The owner needs maintainability, security, and control without unnecessary distributed-systems burden.

## Decision

Build SuperSurf Billing as a Django modular monolith with bounded modules:

- core
- users
- subscribers
- billing
- payments
- network
- support
- audit

Use PostgreSQL as the source of truth and Celery for asynchronous jobs.

## Consequences

Positive:

- Simple deployment and maintenance.
- Mature Django security defaults.
- Strong transactional boundaries for payments and ledger entries.
- Easier backups and local debugging.

Tradeoffs:

- Requires discipline to keep module boundaries clear.
- Very large scale may eventually require extraction, but that is not an MVP concern.

## Rejected Alternatives

- Microservices: unnecessary operational complexity.
- Serverless functions: poor fit for RADIUS, RouterOS, ledger, and local owner operations.
- Full SPA frontend: more complexity than needed for operator workflows.

