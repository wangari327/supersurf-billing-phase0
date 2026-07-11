# Rejected Or Deferred Components

## Rejected

| Component | Reason |
| --- | --- |
| python-daraja | Latest checked release was 2022-04-07. Too stale for payment-critical Daraja code. |
| mpesa-sdk | Latest checked release was 2020-07-22. Too stale for payment-critical Daraja code. |
| django-freeradius | Version 0.1 only in registry check. Not a serious foundation for SuperSurf RADIUS integration. |
| Custom phone parser | Maintained metadata-backed libraries exist. |
| Full frontend SPA | Not justified for server-rendered operator workflows. |
| Microservices | Not justified for one owner-operated ISP MVP. |
| Kubernetes | Excessive operational burden for MVP. |
| Kafka | Excessive for payment/provisioning jobs. |
| MongoDB | Poor fit for transactional ledger and relational subscriber data. |
| Elasticsearch | Not needed for MVP reports and search. |
| STK Push in initial MVP | Not required by Phase 0; incoming Paybill/Till recording is safer first. |

## Deferred

| Component | Reason |
| --- | --- |
| django-daraja | May be tested only if sandbox proof shows compatibility with current Daraja behavior. |
| librouteros | Evaluate in RouterOS lab phase. |
| routeros-api | Evaluate in RouterOS lab phase. |
| pyrad | Evaluate CoA/Disconnect behavior in lab with MikroTik and FreeRADIUS. |
| django-import-export | Useful for admin imports, but M-PESA reconciliation needs a custom mapping layer. |
| django-money | Useful but must not undermine integer minor-unit storage. |
| django-ledger | Too broad for MVP, but useful as an architecture reference. |
| django-hordak | Too broad for MVP, but useful as an architecture reference. |

