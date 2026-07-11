# Entity-Relationship Model

This is a Phase 0.5 logical model, not a production migration.

## Implemented Through Phase 3

```mermaid
erDiagram
    ORGANIZATION ||--|| ORGANIZATION_BRANDING : has
    STAFF_USER ||--o{ AUDIT_EVENT : causes
    SUBSCRIBER ||--o{ SERVICE : owns

    ORGANIZATION {
        uuid id
        string trading_name
        string product_name
        string country_code
        string currency
        string timezone
    }
    STAFF_USER {
        int id
        string username
        string email
        string display_name
        bool is_active
    }
    AUDIT_EVENT {
        bigint id
        string action
        string target_type
        string target_identifier
        json safe_metadata
        datetime created_at
    }
    PLAN {
        uuid id
        string name
        int download_speed_mbps
        int price_minor
        string currency
        int duration_days
        int grace_period_hours
        bool is_active
    }
    SUBSCRIBER {
        uuid id
        string account_number
        string customer_type
        string display_name
        string primary_phone
        string email
        bool is_active
    }
    SERVICE {
        uuid id
        uuid subscriber_id
        int service_number
        string service_reference
        string label
        bool is_active
    }
```

`PLAN` is deliberately not connected to `SERVICE` in Phase 3. Package assignment, subscriptions, billing, PPPoE credentials, RADIUS, RouterOS, provisioning, payments, wallets, ledgers, installation, and equipment entities remain future work.

## Future Logical Model

```mermaid
erDiagram
    ORGANIZATION ||--o{ ORGANIZATION_SETTING : owns
    ORGANIZATION ||--o{ PAYMENT_PROVIDER_PROFILE : configures
    ORGANIZATION ||--o{ STAFF_USER : employs
    STAFF_USER ||--o{ AUDIT_EVENT : causes

    SUBSCRIBER ||--o{ SERVICE : owns
    SUBSCRIBER ||--o{ SUBSCRIBER_PHONE : has
    SUBSCRIBER ||--o{ PAYER_NUMBER : authorizes
    SUBSCRIBER ||--o{ SUPPORT_TICKET : opens

    SERVICE ||--|| SERVICE_LOCATION : installed_at
    SERVICE ||--o{ SUBSCRIPTION : has
    SERVICE ||--o{ RADIUS_ACCOUNT : provisioned_as
    SERVICE ||--o{ NETWORK_SESSION : creates

    PLAN ||--o{ SUBSCRIPTION : prices
    SUBSCRIPTION ||--o{ RENEWAL_CHARGE : creates
    SUBSCRIPTION ||--o{ INVOICE : billed_by

    SUBSCRIBER ||--|| WALLET : owns
    WALLET ||--o{ LEDGER_ENTRY : records
    INVOICE ||--o{ LEDGER_ENTRY : settled_by

    PAYMENT_PROVIDER_PROFILE ||--o{ WEBHOOK_EVENT : receives
    PAYMENT_PROVIDER_PROFILE ||--o{ PAYMENT : identifies
    WEBHOOK_EVENT ||--o| PAYMENT : records
    PAYMENT ||--o{ PAYMENT_ALLOCATION : allocates
    PAYMENT ||--o| UNMATCHED_PAYMENT_CASE : may_open
    PAYMENT ||--o| RECONCILIATION_ITEM : reconciles
    PAYMENT ||--o{ RECEIPT : receipts
    PAYMENT_ALLOCATION ||--o{ LEDGER_ENTRY : posts
    PAYMENT_ALLOCATION ||--o| PAYMENT_ALLOCATION : reverses
    PAYMENT_ALLOCATION }o--o| AUDIT_EVENT : audited_by

    MPESA_STATEMENT_IMPORT ||--o{ MPESA_STATEMENT_ROW : contains
    MPESA_STATEMENT_ROW ||--o| RECONCILIATION_ITEM : reconciles

    NAS_ROUTER ||--o{ NETWORK_SESSION : reports
    NAS_ROUTER ||--o{ PROVISIONING_JOB : executes
    SERVICE ||--o{ PROVISIONING_JOB : changes

    SUPPORT_TICKET ||--o{ SUPPORT_NOTE : contains
    SUPPORT_TICKET }o--|| STAFF_USER : assigned_to

    ORGANIZATION {
        uuid id
        string trading_name
        string product_name
        string primary_brand
        string locale
        string timezone
        string currency
    }
    PAYMENT_PROVIDER_PROFILE {
        uuid id
        uuid organization_id
        string provider
        string product_type
        string environment
        string external_identifier
        bool enabled
        string credential_reference
        json callback_configuration
        json reconciliation_configuration
    }
    SUBSCRIBER {
        uuid id
        string account_number
        string customer_type
        string display_name
        string primary_phone
        string email
        bool is_active
        datetime created_at
    }
    SERVICE {
        uuid id
        uuid subscriber_id
        int service_number
        string service_reference
        string label
        bool is_active
        datetime created_at
    }
    PLAN {
        uuid id
        string name
        bigint price_minor
        string currency
        int duration_value
        string duration_unit
        string renewal_anchor_policy
        int grace_duration_value
        string grace_duration_unit
        string expiry_timezone
        string radius_profile
    }
    SUBSCRIPTION {
        uuid id
        uuid service_id
        uuid plan_id
        datetime starts_at_utc
        datetime expires_at_utc
        datetime grace_until_utc
        string status
    }
    WEBHOOK_EVENT {
        uuid id
        uuid provider_profile_id
        string event_type
        string external_event_id
        json raw_payload
        string processing_status
        datetime received_at
    }
    PAYMENT {
        uuid id
        uuid provider_profile_id
        string provider_transaction_id
        bigint amount_minor
        string currency
        string channel
        string lifecycle
        datetime received_at
    }
    PAYMENT_ALLOCATION {
        uuid id
        uuid payment_id
        uuid subscriber_id
        uuid wallet_id
        uuid invoice_id
        uuid renewal_charge_id
        bigint amount_minor
        string allocation_type
        uuid allocated_by_id
        string allocated_by_type
        string idempotency_key
        datetime allocated_at
        uuid reverses_allocation_id
        uuid audit_event_id
    }
    UNMATCHED_PAYMENT_CASE {
        uuid id
        uuid payment_id
        string reason
        string status
        datetime opened_at
        datetime resolved_at
    }
    LEDGER_ENTRY {
        uuid id
        uuid wallet_id
        bigint debit_minor
        bigint credit_minor
        string currency
        string entry_type
        datetime posted_at
    }
    NAS_ROUTER {
        uuid id
        string name
        string environment
        string nas_identifier
        string nas_ip_address
        string management_address
        string secret_reference
        bool enabled
        datetime last_credential_rotation_at
    }
    PROVISIONING_JOB {
        uuid id
        uuid service_id
        string action
        string status
        int attempt_count
        bool dry_run
    }
    AUDIT_EVENT {
        uuid id
        string actor_type
        uuid actor_id
        string action
        string object_type
        uuid object_id
        datetime created_at
    }
```

## Payment Model Notes

- Every valid provider transaction creates one canonical `Payment`, even when it cannot yet be matched to a subscriber.
- `UnmatchedPaymentCase` is not an alternative to `Payment`; it is an optional case opened for a canonical payment.
- `PaymentAllocation` records allocation of payment value to a subscriber, wallet, invoice, or renewal charge.
- Allocations must not be mutated silently. Corrections require reversal or compensating allocation records linked through `reverses_allocation_id`.
- Payment lifecycle values should include `received`, `unmatched`, `partially_allocated`, `allocated`, `reversed`, `refunded_externally`, and `rejected` only when no valid financial transaction exists.
- Provider transaction identifiers are unique within a composite boundary such as `(provider_profile_id, environment, provider_transaction_id)`, not globally.
- A sandbox transaction must not collide with a production transaction.

## Provider Profile Notes

`PaymentProviderProfile` separates Paybill and Till products, sandbox and production environments, shortcode or Till identifier, enabled state, credential reference, callback configuration, and reconciliation configuration.

Credentials must not be stored directly in ordinary display fields. Store only encrypted secrets or secret-provider references.

## Plan Duration Notes

- Use `duration_value` and `duration_unit`, where unit can be `days`, `weeks`, or `calendar_months`.
- Thirty days is not always the same as one calendar month.
- Calendar-month renewal must define a renewal anchor policy and handle month-end dates.
- Persist timestamps in UTC.
- Perform business expiry and grace calculations in Africa/Nairobi.

## Network Notes

- Each NAS/router has its own shared secret or secret reference.
- Each NAS/router records NAS-Identifier, NAS-IP-Address or private management address, enabled state, lab or production environment, and last credential rotation time.
- Never display full RADIUS secrets after initial entry.
- RADIUS secrets must be encrypted or loaded through a secret provider.
- RADIUS tables may include official FreeRADIUS tables alongside SuperSurf-owned service and provisioning tables.
