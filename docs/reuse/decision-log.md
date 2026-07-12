# Reuse Decision Log

## D001: Use Django Auth Instead Of Custom Authentication

Decision: adopt Django auth.

Reason: authentication, password hashing, sessions, CSRF integration, and permissions are mature and maintained in Django.

## D002: Defer Broad Phone Metadata Library Until Needed

Decision: Phase 0 preferred adopting `phonenumbers` behind a broader normalizer. Phase 3 supersedes that for the narrow subscriber registry in D016 and uses the approved Kenya-only examples directly.

Reason: Phase 3 accepts only a small, owner-approved set of Kenya input formats and must avoid adding dependencies outside the narrow registry scope. A metadata-backed library should be reconsidered if later phases need broader international or landline support.

## D003: Implement SuperSurf Ledger Minimally In-House

Decision: implement a narrow append-only wallet and ledger model in-house.

Reason: full accounting packages are broader than the MVP and may add complexity. SuperSurf needs prepaid wallet allocation, renewal, reversals, and auditability, not a complete accounting suite.

## D004: Reject Stale Daraja Wrappers For MVP

Decision: reject `python-daraja` and `mpesa-sdk`; treat `django-daraja` as rejected unless sandbox proof changes the decision.

Reason: latest checked releases are stale for payment-critical code. Use official Daraja documentation, `httpx`, `tenacity`, fixtures, and tests behind `MpesaProvider`.

## D005: Use Official FreeRADIUS SQL Boundary

Decision: use FreeRADIUS as an external system and validate official SQL integration in lab.

Reason: RADIUS protocol and accounting behavior are mature, operationally sensitive, and should not be invented inside the billing app.

## D006: Wrap RouterOS API Packages

Decision: evaluate `librouteros` and `routeros-api`, but only behind `RouterOSAdapter`.

Reason: RouterOS package choice may change after TLS, certificate, and command tests. Business logic must not call package APIs directly.

## D007: Keep UI Server-Rendered

Decision: use Django templates, HTMX, and Tailwind; avoid React/Next/Vue/Angular in MVP.

Reason: the operator dashboard needs speed, maintainability, RBAC integration, and low JavaScript, not a large frontend application.

## D008: Keep Phase 1 Foundation Lean

Decision: Phase 1 creates only `core`, `users`, and `audit` apps. It must not create payment, subscriber, billing, RADIUS, RouterOS, wallet, ledger, or provisioning models.

Reason: the owner approved a foundation phase only. Keeping later domains out of Phase 1 prevents empty scaffolding and premature migrations.

## D009: Use Canonical Payment Plus Allocation Model

Decision: every valid provider transaction creates one canonical `Payment`; matching and value application are represented by `PaymentAllocation`, and unresolved matching opens an optional `UnmatchedPaymentCase`.

Reason: unmatched payments are still valid financial transactions. Treating them as an alternative to `Payment` would make reconciliation, reversals, idempotency, and audit history harder to reason about.

## D010: Scope Provider Transaction Uniqueness By Profile And Environment

Decision: provider transaction identifiers must be unique within a composite boundary such as provider profile, environment, and provider transaction identifier.

Reason: sandbox and production transactions must not collide, and Paybill and Till products may have independent identifier spaces.

## D011: Use Django Groups And Permissions For Phase 1 RBAC

Decision: use Django's built-in Groups and Permissions for Phase 1 roles. Do not install django-guardian, rules, or django-role-permissions.

Reason: Phase 1 permissions are global staff and settings permissions. Object-level authorization is not required until later subscriber, payment, or network domains exist.

## D012: Implement Explicit SuperSurf AuditEvent

Decision: create a project-owned append-only `AuditEvent` model and service instead of installing django-simple-history, django-auditlog, or django-reversion in Phase 1.

Reason: Phase 1 needs explicit security and settings audit events with redaction. Generic history packages would add dependency weight before business-domain models exist.

## D013: Use redis-py 6.4.0 With Valkey Target

Decision: select redis-py 6.4.0 for Celery's Redis protocol transport and use a Valkey 8 container in Compose.

Reason: Celery/Kombu 5.6.3 rejects redis-py 8.x through its dependency constraints. redis-py 6.4.0 resolves cleanly and speaks the Redis protocol needed by Valkey.

## D014: Keep Caddy Optional In Phase 1

Decision: include Caddy only in an optional local preview Compose profile.

Reason: ordinary localhost development should not require a public domain or TLS reverse proxy. The Phase 1 Compose stack uses Django `runserver`; Caddy in this repository is not a production WSGI deployment.

## D015: Add Package Catalog Before Subscriber Work

Decision: Phase 2 creates the `billing.Plan` package catalog only. Operators see the term "Package", while the internal model stays `Plan`. Packages store KES prices as integer minor units, use 30-day duration and 24-hour grace defaults, and are deactivated rather than deleted.

Reason: SuperSurf needs a reviewed package catalog before subscriptions, renewals, payments, wallets, invoices, discounts, RADIUS, RouterOS, or network provisioning can safely refer to package definitions.

## D016: Add Subscriber Registry Before Subscriptions

Decision: Phase 3 creates only `Subscriber`, `Service`, and one internal sequence/allocation model. Subscriber account numbers and service references are backend-generated and immutable. The Phase 3 phone normalizer stays Kenya-only and handles only the approved input shapes instead of adding a broader phone metadata dependency.

Reason: SuperSurf needs stable subscriber and service identifiers before later subscription, billing, payment, RADIUS, PPPoE, RouterOS, installation, or equipment domains can reference them. Keeping Phase 3 narrow avoids collecting sensitive identity, location, billing, and network data before those later workflows are reviewed.

## D017: Add Manual Package Assignment Before Billing

Decision: Phase 4 creates `billing.Subscription` as immutable package-assignment history with package snapshots. It does not create charges, invoices, wallets, ledgers, renewals, payment records, RADIUS rows, PPPoE credentials, RouterOS calls, or provisioning jobs.

Reason: Operators need a safe way to record which package applies to a service before any billing, renewal, payment, or network automation depends on that relationship. Snapshotting package terms preserves history when package definitions change later.

## D018: Add Manual Billing Periods Before Payments

Decision: Phase 5 creates `billing.BillingPeriod` as append-only manual access-period history with snapshots copied from the active subscription. It supports manual activation and renewal, operation ID idempotency, stale-form checks, derived billing state, and PostgreSQL-tested sequence allocation. It does not create charges, invoices, wallets, ledgers, payment records, M-PESA records, automatic renewals, automatic suspension, RADIUS rows, PPPoE credentials, RouterOS calls, provisioning jobs, customer portals, notifications, installation fees, or equipment billing.

Reason: Operators need a reviewed way to record access periods and apply approved renewal date rules before any money movement or network enforcement is connected to the platform. Keeping payment claims and network actions out of Phase 5 prevents manual renewal from being mistaken for received revenue or actual service suspension/reactivation.
