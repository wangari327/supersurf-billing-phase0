# SuperSurf Repository Instructions

This repository is for SuperSurf Billing, a Kenya-first ISP billing and subscriber-management platform for SuperSurf.

## Current Phase

This repository has completed Phase 0 through Phase 8, Phase 9 Daraja sandbox callback evidence capture, and the explicitly approved Phase 9.1 sandbox Paybill canonical payment adapter.

Do not begin Phase 9.2 or a later phase. Do not add Till or production payment processing, Paybill or Till credentials, Safaricom or Daraja outbound calls, STK payment processing, reconciliation imports, invoices, receipts, customer portals, notifications, automatic Wallet spending, automatic renewal, expiry or suspension automation, RADIUS, PPPoE credentials, RouterOS, provisioning, installation fees, equipment billing, live router access, or production credentials without explicit Owner approval.

Phase 3 subscriber identifiers are backend generated and immutable:

- Subscriber account numbers use `SS000001` through the internal account sequence.
- Service references use `SS000001-01` through `SS000001-99` per subscriber.
- A future PPPoE username convention may lowercase the service reference, such as `ss000001-01`, but the repository must not add PPPoE fields or credentials in Phase 3.

## Brand Rules

- The default brand is SuperSurf.
- The default billing product name is SuperSurf Billing.
- Related labels are SuperSurf Networks, SuperSurf Support, SuperSurf Portal, SuperSurf Payments, SuperSurf NOC, SuperSurf Reports, SuperSurf Radius, and SuperSurf Connect.
- Do not use placeholder brands such as Example ISP, Sample Company, Demo Telecom, MyISP, Acme, Foo, Bar, or Tenant One.
- Do not invent domains, email addresses, Paybill numbers, Till numbers, KRA PINs, business registration numbers, licence numbers, API credentials, or production credentials.
- Any real-world value not supplied by SuperSurf must remain empty, marked not configured, editable through secure settings, and blocked where required for production activation.

## Kenya-First Defaults

Fresh installations must default to:

- Country: Kenya
- ISO country code: KE
- Currency: KES
- Currency display label: KSh
- Business timezone: Africa/Nairobi
- Database timestamp storage: UTC
- User-facing locale: en-KE
- Default language: English
- Date display: DD/MM/YYYY
- Time display: 24-hour
- Week start: Monday
- Default telephone country code: +254

Money must be stored as integer minor units. Never use binary floating-point values for ledger or payment amounts.

Phase 2 package prices are stored as integer KES minor units and entered by operators as ordinary KSh values. Discounts remain future work and must not be hard-coded into packages.

Phase 3 subscriber phone normalization accepts only Kenya formats in the approved examples, stores normalized `+254...` values, and must not collect national ID, passport, KRA PIN, company registration, date of birth, gender, installation location, wallet, package, billing, M-PESA, payer, RADIUS, PPPoE, router, or equipment fields.

Phase 4 subscriptions are manual package-assignment history only. `billing.Subscription` snapshots package terms at assignment time, stores integer KES minor units, permits only `active` and `ended` states, and must not create charges, invoices, renewals, expiry enforcement, payments, wallet or ledger entries, RADIUS rows, PPPoE credentials, RouterOS calls, provisioning jobs, notifications, installation fees, or equipment billing.

Phase 5 billing periods are manual access-period history only. `billing.BillingPeriod` snapshots the active `Subscription`, uses 30-day package periods and the default 24-hour grace from subscription snapshots unless the source package terms differ, derives billing state at read time, and supports manual activation and renewal with operator reasons, operation IDs, and stale-form checks. Early renewal preserves remaining days, grace renewal extends from the original expiry, late renewal starts at the renewal timestamp, and each service has independent periods. Phase 5 must not claim payment receipt, automatically renew, automatically suspend, enforce network access, create charges, create invoices, create wallet or ledger entries, call M-PESA, create Celery expiry jobs, create RADIUS/PPPoE/RouterOS/provisioning behavior, or add customer-portal, installation-fee, equipment-billing, or notification workflows.

Phase 6 wallets and ledger entries are account-level accounting records only. `billing.Wallet` belongs to a subscriber, not a service. It stores no mutable balance, payment reference, M-PESA transaction ID, invoice balance, package link, or service link. `billing.LedgerEntry` is append-only, stores integer KES minor units, and derives balance from the latest ledger sequence. Manual credits are not proof of payment. Manual debits are accounting corrections, not package charges or invoices. Corrections use reversal entries rather than editing or deletion. Balances may not become negative. Partial and overpayments may later remain as wallet credit, but payment integration is not implemented in Phase 6.

Phase 7 Wallet-funded service-time charges are manual operator actions only. `billing.BillingCharge` links one `BillingPeriod` to one `billing_charge` ledger debit against an existing subscriber Wallet. Activation requires no existing billing period; renewal requires the latest billing period as the expected previous period. The charge amount is exactly the active `Subscription` snapshot price, partial Wallet balances are rejected, and overpayment remains Wallet credit. Billing-charge entries are not manually reversible. Phase 7 must not record payments, M-PESA transactions, invoices, receipts, discounts, bundles, customer-specific prices, automatic wallet allocation, automatic renewal, network enforcement, RADIUS/PPPoE/RouterOS/provisioning behavior, customer-portal, installation-fee, equipment-billing, or notification workflows.

Phase 8 canonical payment foundation records provider-neutral `billing.Payment` rows, one full-wallet `billing.PaymentAllocation` per payment, `payment_credit` ledger entries, and `billing.UnmatchedPaymentCase` rows. Only active fake provider profiles in test or sandbox environments may ingest payments, and fake ingestion is blocked when `SUPERSURF_ENVIRONMENT=PRODUCTION`. Matched `SS000001`-style account references credit the subscriber account Wallet; unmatched, malformed, missing, unknown, and service-reference inputs remain valid payments with open unmatched cases. Phase 8 must not make Safaricom or Daraja calls, ingest real M-PESA callbacks, store Paybill or Till credentials, run STK Push, import reconciliation statements, create invoices or receipts, automatically spend Wallet credit, automatically renew services, or perform network enforcement.

Phase 9 stores inbound Daraja sandbox callbacks as immutable, sanitized evidence. Phase 9.1 permits only an explicitly enabled public-LAB M-PESA Paybill `c2b_confirmation` to enter the existing canonical payment flow. The processor must read immutable event fields, require the synchronized active sandbox Paybill profile, use deterministic idempotency, create system-sourced accounting rows with no human actor, and atomically create one callback-to-payment link. Validation and STK callbacks remain evidence only. Till, production, reconciliation, renewal, and network behavior remain out of scope.

## Reuse-First Engineering

Follow this order before writing custom code:

1. Existing Django or Python functionality
2. Official project functionality
3. Official schemas or reference implementations
4. Mature maintained open-source packages
5. Lightweight reusable components
6. Minimal SuperSurf-specific custom code

Before writing more than roughly 100 lines for generic technical capability, document why an existing package was not adopted in `docs/reuse/decision-log.md`.

## Security Rules

- Never commit production secrets.
- Never log M-PESA secrets, OAuth tokens, router passwords, RADIUS shared secrets, WireGuard private keys, encryption keys, session cookies, or full identity numbers.
- Integration credentials must be encrypted at rest and access-controlled.
- Webhook processing must be idempotent.
- Financial records must be append-only and must not be hard-deleted.
- Router writes must default to dry-run until explicitly configured and approved.
- WAN, routing, CAKE, WireGuard, watchdog, and unrelated router settings are out of scope unless a later reviewed phase explicitly includes them.

## Phase Gates

At the end of every implementation phase:

- Run automated tests.
- Run linters.
- Run type checks where configured.
- Run security checks.
- List files changed.
- Describe database migrations.
- Document commands used.
- List adopted dependencies.
- Update third-party notices.
- Identify unresolved risks.
- Update the implementation checklist.
- Stop for review.

Never continue automatically to the next phase.
