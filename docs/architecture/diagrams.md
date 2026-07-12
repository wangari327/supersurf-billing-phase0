# Architecture Diagrams

## Component Diagram

```mermaid
flowchart LR
    Staff["SuperSurf staff"] --> Web["Django web app"]
    Web --> DB[("PostgreSQL")]
    Web --> Broker["Redis or reviewed broker"]
    Broker --> Worker["Celery workers"]
    Worker --> DB
    Scheduler["Celery Beat or reviewed scheduler"] --> Broker
    Mpesa["Future Safaricom Daraja callbacks"] --> Caddy["Caddy TLS reverse proxy"]
    Caddy --> Web
    Radius["FreeRADIUS"] --> DB
    Worker --> RadiusClient["RADIUS CoA client"]
    RadiusClient --> Radius
    Worker --> RouterAdapter["RouterOSAdapter"]
    RouterAdapter --> Router["MikroTik RouterOS"]
    Router --> Radius
    Backup["Backup jobs"] --> BackupStore["Encrypted backup storage"]
    Worker --> Backup
```

## Deployment Diagram

```mermaid
flowchart TB
    Internet["Internet"] --> Caddy["Caddy reverse proxy"]
    Caddy --> App["Django app container"]
    App --> Postgres[("PostgreSQL")]
    App --> Redis["Redis or reviewed broker"]
    Redis --> Celery["Celery worker"]
    Redis --> Beat["Scheduler"]
    Celery --> Postgres
    Beat --> Redis
    FreeRADIUS["FreeRADIUS container or host package"] --> Postgres
    MikroTik["MikroTik RouterOS lab or production router"] --> FreeRADIUS
    Celery --> MikroTik
    Celery --> FreeRADIUS
    Backup["Backup process"] --> Offsite["Encrypted off-site copy"]
```

## Phase 8 Fake Payment Data Flow

```mermaid
sequenceDiagram
    participant Staff as Administrator or Finance
    participant Web as Django payment UI
    participant DB as PostgreSQL
    participant Billing as Billing service

    Staff->>Web: Submit fake payment
    Web->>Billing: ingest_fake_payment
    Billing->>DB: Lock provider profile and canonical payment
    Billing->>DB: Match SS account reference
    alt matched account reference
        Billing->>DB: Lock subscriber, wallet, and latest ledger entry
        Billing->>DB: Create PaymentAllocation and payment_credit LedgerEntry
    else missing, malformed, or unknown reference
        Billing->>DB: Create UnmatchedPaymentCase
    end
    Billing->>DB: Record audit events
```

Future M-PESA, Paybill, or Till adapters should call the same canonical payment service only after Daraja sandbox evidence and provider-specific controls are reviewed.

## Network Action Flow

```mermaid
sequenceDiagram
    participant User as Authorized staff or billing job
    participant App as Django service
    participant DB as PostgreSQL
    participant Worker as Network worker
    participant Radius as FreeRADIUS/CoA
    participant Router as MikroTik RouterOS

    User->>App: Request retry/disconnect/provision
    App->>DB: Validate permission and create audited job
    App->>Worker: Enqueue job
    Worker->>DB: Check dry-run and allowlist
    Worker->>Radius: Apply RADIUS or CoA action where allowed
    Worker->>Router: Apply RouterOS action where allowed
    Worker->>DB: Store result, retries, and audit event
```
