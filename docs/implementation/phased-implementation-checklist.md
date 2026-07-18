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

- [x] Django project.
- [x] Docker Compose.
- [x] PostgreSQL development option.
- [x] Broker and Celery.
- [x] Reverse proxy development configuration.
- [x] Staff authentication.
- [x] RBAC.
- [x] SuperSurf organization seed.
- [x] Configurable branding.
- [x] Base UI.
- [x] Audit framework.
- [x] CI.
- [x] Initial tests.
- [x] Stop for approval.

## Phase 1.1: Security Hardening

- [x] Audit redaction and append-only protections.
- [x] Role boundary corrections.
- [x] Admin bypass prevention.
- [x] Sensitive settings permissions.
- [x] Production fail-closed settings.
- [x] Regression tests.
- [x] Stop for approval.

## Phase 2: Package Catalog

- [x] Packages.
- [x] KES minor-unit pricing.
- [x] Initial package seed migration.
- [x] Audited package create/update/status workflows.
- [x] Package permissions.
- [x] Tests.
- [x] Stop for approval.

## Phase 3: Subscriber Registry

- [x] Subscriber accounts.
- [x] Service references.
- [x] Backend-generated immutable identifiers.
- [x] Kenya phone normalization.
- [x] Audited subscriber and service create/update/status workflows.
- [x] Subscriber and service permissions.
- [x] Dashboard and navigation updates.
- [x] Tests.
- [x] Stop for approval.

## Phase 4: Package Assignments

- [x] Manual package assignment.
- [x] Immutable subscription history.
- [x] Package snapshot fields.
- [x] One active subscription per service.
- [x] Audited assignment, package change, and ending workflows.
- [x] Subscription permissions.
- [x] Tests.
- [x] Stop for approval.

## Phase 5: Billing Periods And Manual Renewals

- [x] Billing period model.
- [x] Immutable subscription snapshots on each period.
- [x] Manual activation.
- [x] Manual renewal.
- [x] Early, grace, late, and zero-hour grace date rules.
- [x] Derived billing state.
- [x] Operation ID idempotency and stale-form checks.
- [x] Billing-period permissions.
- [x] Paginated period history.
- [x] PostgreSQL concurrency tests.
- [x] Tests.
- [x] Stop for approval.

## Phase 6: Wallet And Append-Only Ledger Foundation

- [x] Account-level wallet model.
- [x] Append-only ledger entry model.
- [x] Manual credit workflow.
- [x] Manual debit workflow.
- [x] Reversal workflow.
- [x] Derived wallet balance from latest ledger sequence.
- [x] Operation ID idempotency.
- [x] Wallet and ledger permissions.
- [x] PostgreSQL concurrency tests.
- [x] Tests.
- [x] Stop for approval.

## Phase 7: Wallet-Funded Activation And Renewal Charges

- [x] Immutable billing-charge model.
- [x] Billing-charge ledger entry type.
- [x] Wallet-funded activation workflow.
- [x] Wallet-funded renewal workflow.
- [x] Exact active subscription snapshot pricing.
- [x] Sufficient-balance enforcement with overpayment left as Wallet credit.
- [x] Operation ID idempotency and stale-form checks.
- [x] Billing-charge permissions.
- [x] Manual uncharged UI labeling.
- [x] PostgreSQL concurrency tests.
- [x] Tests.
- [x] Stop for approval.

## Phase 8: Canonical Payments And Wallet Credits

- [x] Provider-neutral payment provider profile model.
- [x] Immutable canonical payment model.
- [x] Immutable full-wallet payment allocation model.
- [x] Unmatched payment case model and resolution workflow.
- [x] `payment_credit` ledger entry type.
- [x] Fake provider ingestion for development and tests.
- [x] Production block for fake payment ingestion.
- [x] Exact `SS000001` account-reference matching.
- [x] Matched payment Wallet credits.
- [x] Missing, malformed, service-reference, and unknown-reference unmatched cases.
- [x] Provider transaction idempotency and operation ID conflict checks.
- [x] Payment and unmatched-case permissions.
- [x] Operator UI for payment list, fake intake, detail, unmatched list, and resolution.
- [x] PostgreSQL concurrency tests.
- [x] Tests.
- [x] Stop for approval.

## Phase 9: Daraja Sandbox Callback Evidence

- [x] Provider-neutral tokenized callback routes.
- [x] C2B validation, C2B confirmation, and STK result evidence capture.
- [x] Recursive sensitive-value redaction and deterministic payload hashing.
- [x] Append-only callback events and database-backed idempotency.
- [x] Read-only Administrator and Finance operator interface.
- [x] Controlled sandbox registration and delivery evidence.
- [x] Stop for approval.

## Phase 9.1: Sandbox Paybill Canonical Payment Adapter

- [x] Explicit public-LAB enable gate and fail-closed configuration.
- [x] Idempotent sandbox Paybill provider-profile synchronization.
- [x] Safe `BusinessShortCode` extraction into callback evidence.
- [x] Conflicting duplicate payload detection.
- [x] C2B confirmation-only canonical payment processing.
- [x] Existing account-reference matching and unmatched-case behavior.
- [x] System/operator accounting provenance constraints.
- [x] Append-only callback-to-payment links.
- [x] Permission-respecting callback and Payment cross-links.
- [x] SQLite regression coverage and PostgreSQL concurrency coverage.
- [x] Owner-deployed controlled live sandbox Paybill payment verification.
- [x] Stop before Phase 9.2.

## Future Phase: Billing And Payments

- [ ] Invoices.
- [ ] Receipts.
- [ ] Renewal engine.
- [ ] Expiry and suspension automation.
- [ ] Reports.
- [ ] Tests.
- [ ] Stop for approval.

## Future Phase: M-PESA

- [x] Validated Daraja research for Phase 9 evidence capture.
- [x] Sandbox callback evidence setup.
- [x] Phase 9.1 inbound sandbox Paybill confirmation adapter.
- [ ] Till adapter.
- [x] Append-only callback persistence.
- [x] Callback and canonical-payment idempotency for the approved Paybill scope.
- [x] Sandbox Paybill confirmation matching into the canonical payment service.
- [ ] STK payment processing.
- [ ] Production M-PESA processing.
- [ ] Reconciliation.
- [ ] Tests.
- [ ] Stop for approval.

## Future Phase: FreeRADIUS

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

## Future Phase: MikroTik

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

## Future Phase: Controlled Pilot

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

## Future Phase: Production Hardening

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
