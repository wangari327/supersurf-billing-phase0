# Entity-Relationship Model

This is a Phase 0 logical model, not a production migration.

```mermaid
erDiagram
    ORGANIZATION ||--o{ ORGANIZATION_SETTING : owns
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
    PAYMENT ||--o{ LEDGER_ENTRY : funds
    PAYMENT ||--o{ RECEIPT : receipts
    INVOICE ||--o{ LEDGER_ENTRY : settled_by

    MPESA_CALLBACK ||--o| PAYMENT : creates
    MPESA_CALLBACK ||--o| UNMATCHED_PAYMENT : creates
    MPESA_STATEMENT_IMPORT ||--o{ MPESA_STATEMENT_ROW : contains
    MPESA_STATEMENT_ROW ||--o| RECONCILIATION_ITEM : reconciles
    PAYMENT ||--o| RECONCILIATION_ITEM : reconciles

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
    SUBSCRIBER {
        uuid id
        string account_number
        string display_name
        string status
        datetime created_at
    }
    SERVICE {
        uuid id
        uuid subscriber_id
        string status
        datetime activated_at
        datetime suspended_at
    }
    PLAN {
        uuid id
        string name
        bigint price_minor
        string currency
        int duration_days
        string radius_profile
    }
    SUBSCRIPTION {
        uuid id
        uuid service_id
        uuid plan_id
        datetime starts_at
        datetime expires_at
        datetime grace_until
        string status
    }
    PAYMENT {
        uuid id
        string provider
        string provider_transaction_id
        bigint amount_minor
        string currency
        string channel
        string matching_status
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

## Model Notes

- `Payment.provider_transaction_id` must be unique per provider.
- Ledger entries are append-only.
- Reversals create compensating entries.
- `UnmatchedPayment` keeps a link to the original callback and can later be manually resolved.
- `Service` exists separately from `Subscriber` to allow future multi-service customers without redesigning payments and network provisioning.
- RADIUS tables may include official FreeRADIUS tables alongside SuperSurf-owned service and provisioning tables.

