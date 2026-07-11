# ADR 0002: Use Django Templates, HTMX, And Tailwind CSS

## Status

Proposed for Phase 1.

## Context

The operator UI should be fast, maintainable, accessible, and low-JavaScript. SuperSurf does not need a heavy frontend framework for the MVP.

## Decision

Use Django templates, HTMX for targeted interactivity, Tailwind CSS for styling, and minimal Alpine.js only where necessary.

## Consequences

Positive:

- Keeps UI close to Django permissions, forms, and server-side validation.
- Reduces frontend build and state-management complexity.
- Supports responsive operator workflows with small JavaScript surface.

Tradeoffs:

- Some rich interactions need careful HTMX patterns.
- Component reuse needs disciplined template organization.

## Rejected Alternatives

- React, Next.js, Vue, Angular: not justified for the initial operator dashboard.
- Marketing-site architecture: the first screen should be the actual usable dashboard after login.

