# ADR 0006: Use Official FreeRADIUS SQL Boundary

## Status

Proposed for Phase 4 validation.

## Context

FreeRADIUS already provides mature SQL authorization and accounting patterns. SuperSurf should not invent a RADIUS database schema without justification.

## Decision

Use the official FreeRADIUS PostgreSQL SQL integration as the boundary for RADIUS authentication and accounting, subject to licence and deployment review.

SuperSurf-owned tables should model subscribers, services, plans, and provisioning jobs. Synchronization to FreeRADIUS-compatible tables should happen through explicit services.

## Consequences

Positive:

- Aligns with FreeRADIUS documentation and operational tooling.
- Avoids custom RADIUS schema mistakes.
- Easier lab testing with standard FreeRADIUS behavior.

Tradeoffs:

- FreeRADIUS project licensing and schema use must be reviewed.
- Some plan attributes need careful translation to RADIUS reply/check items.

