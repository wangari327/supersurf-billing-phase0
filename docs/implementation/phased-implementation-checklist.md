# Phased Implementation Checklist

## Phase 0: Product Specification And Reconnaissance

- [x] Inspect workspace.
- [x] Conduct internet research.
- [x] Research official documentation.
- [x] Research open-source ecosystem.
- [x] Create AGENTS.md.
- [x] Create product and Kenya default docs.
- [x] Create architecture docs.
- [x] Create ADRs.
- [x] Create threat model.
- [x] Create entity-relationship model.
- [x] Create reuse and dependency reports.
- [x] Create Phase 1 checklist.
- [x] Stop before scaffolding application code.

## Phase 1: Foundation

- [ ] Django project.
- [ ] Docker Compose.
- [ ] PostgreSQL.
- [ ] Broker and Celery.
- [ ] Reverse proxy development configuration.
- [ ] Staff authentication.
- [ ] RBAC.
- [ ] SuperSurf organization seed.
- [ ] Configurable branding.
- [ ] Base UI.
- [ ] Audit framework.
- [ ] CI.
- [ ] Initial tests.
- [ ] Stop for approval.

## Phase 2: Subscribers And Billing

- [ ] Subscribers.
- [ ] Service locations.
- [ ] Plans.
- [ ] Subscriptions.
- [ ] Wallet.
- [ ] Append-only ledger.
- [ ] Renewal charges.
- [ ] Renewal engine.
- [ ] Suspension state machine.
- [ ] Reports.
- [ ] Tests.
- [ ] Stop for approval.

## Phase 3: M-PESA

- [ ] Validated Daraja research.
- [ ] Sandbox setup.
- [ ] Paybill adapter.
- [ ] Till adapter.
- [ ] Callback persistence.
- [ ] Idempotency.
- [ ] Matching.
- [ ] Unmatched-payment workflow.
- [ ] Reconciliation.
- [ ] Fake callback tool.
- [ ] Tests.
- [ ] Stop for approval.

## Phase 4: FreeRADIUS

- [ ] FreeRADIUS container or package.
- [ ] PostgreSQL integration.
- [ ] NAS model.
- [ ] Authentication.
- [ ] Accounting.
- [ ] Plan attributes.
- [ ] Test subscribers.
- [ ] Integration tests.
- [ ] Documentation.
- [ ] Stop for approval.

## Phase 5: MikroTik

- [ ] RouterOS adapter.
- [ ] Fake adapter.
- [ ] Dry-run adapter.
- [ ] Real API-TLS adapter.
- [ ] Router health.
- [ ] Session listing.
- [ ] Subscriber disconnect.
- [ ] CoA workflow.
- [ ] Job retries.
- [ ] Audit.
- [ ] Reviewed lab scripts.
- [ ] Tests.
- [ ] Stop for approval.

## Phase 6: Controlled Pilot

- [ ] One test plan.
- [ ] One test subscriber.
- [ ] One test CPE.
- [ ] Sandbox or controlled payment.
- [ ] RADIUS authentication.
- [ ] Accounting.
- [ ] Suspension.
- [ ] Reactivation.
- [ ] Rollback.
- [ ] Pilot report.
- [ ] Stop for explicit production approval.

## Phase 7: Production Hardening

- [ ] Production Compose configuration.
- [ ] TLS.
- [ ] Secrets procedure.
- [ ] Backup automation.
- [ ] Restore test.
- [ ] Monitoring.
- [ ] Rate limits.
- [ ] Security review.
- [ ] Dependency review.
- [ ] Licence review.
- [ ] SuperSurf operator handbook.
- [ ] Migration checklist.
- [ ] Stop for final review.

