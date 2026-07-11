# ADR 0005: Network Integrations Default To Dry-Run

## Status

Proposed for Phase 1 and binding for network phases.

## Context

The live SuperSurf router must not be altered accidentally. Network changes can disrupt customers and are harder to undo than local database changes.

## Decision

All RouterOS and RADIUS write paths default to dry-run until explicitly configured, lab-tested, role-approved, and audited.

## Consequences

Positive:

- Safer development and pilot operation.
- Clear audit trail of intended actions.
- Prevents accidental production disruption.

Tradeoffs:

- Requires an explicit activation step during controlled pilot.
- Support staff must understand pending dry-run state.

