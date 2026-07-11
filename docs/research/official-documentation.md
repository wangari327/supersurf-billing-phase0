# Official Documentation Research

Accessed on 2026-07-11 unless otherwise noted.

## Safaricom Daraja And M-PESA

| Source | Applicable capability | Phase 0 finding | Ambiguity or required sandbox test |
| --- | --- | --- | --- |
| https://developer.safaricom.co.ke/apis | Daraja API catalogue | Official source for available Daraja products and endpoints. Use as the first reference for C2B, transaction status, authentication, and callback behavior. | The web UI is product-oriented and some details require a logged-in developer account or sandbox app. Verify exact Paybill and Till callback payloads in sandbox. |
| https://developer.safaricom.co.ke/apis/PullTransaction | Pull Transaction or transaction lookup capability | Useful for reconciliation and status verification where supported by the configured product. | Confirm product eligibility, identifier fields, rate limits, and response shape for SuperSurf's actual Paybill/Till products. |
| https://developer.safaricom.co.ke/ | Developer portal | Required for sandbox credentials, production app approval, callback URL configuration, and product activation. | SuperSurf must supply sandbox and production credentials later. |

Phase 0 decision: implement Daraja as a thin provider behind `MpesaProvider`, `PaybillProvider`, and `TillProvider`. Do not adopt a stale wrapper without sandbox proof.

## MikroTik RouterOS

| Source | Applicable capability | Phase 0 finding | Ambiguity or required lab test |
| --- | --- | --- | --- |
| https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API | RouterOS API | Official RouterOS API documentation. Use API or API-SSL only through `RouterOSAdapter`. | Verify API-SSL certificate plan and command behavior against CHR or spare router. |
| https://help.mikrotik.com/docs/display/ROS/RADIUS | RouterOS RADIUS | Official RADIUS behavior for RouterOS services, including PPP integration and accounting settings. | Verify PPPoE attributes, interim updates, disconnect behavior, and NAS-Identifier plan in lab. |
| https://help.mikrotik.com/docs/display/ROS/PPP+AAA | PPP AAA with RADIUS | Relevant for PPPoE user authentication through RADIUS. | Confirm exact rate-limit attributes and service profile mapping. |

Phase 0 decision: use a dry-run `RouterOSAdapter` first. Real API-TLS writes require lab validation and Owner approval in later phases.

## FreeRADIUS

| Source | Applicable capability | Phase 0 finding | Ambiguity or required lab test |
| --- | --- | --- | --- |
| https://www.freeradius.org/documentation/ | Official documentation landing | Source for FreeRADIUS modules, SQL, dynamic authorization, and upgrade docs. | Version choice must be validated against container/package availability. |
| https://www.freeradius.org/documentation/freeradius-server/4.0.0/reference/raddb/mods-available/sql.html | SQL module documentation | Documents SQL configuration and database-backed authorization/accounting concepts. | FreeRADIUS 4 docs may not match 3.2 deployment exactly. Validate selected server version. |
| https://wiki.freeradius.org/modules/Rlm_sql | `rlm_sql` module | Established SQL module reference, including database-backed check/reply/accounting workflows. | Confirm PostgreSQL schema and indexes for expected accounting volume. |
| https://www.freeradius.org/documentation/freeradius-server/4.0.0/reference/raddb/sites-available/coa.html | CoA and Disconnect-Request | Dynamic authorization is relevant for disconnect/reactivation workflows. | Must validate CoA support with MikroTik RouterOS in lab. |

Phase 0 decision: use official FreeRADIUS SQL integration patterns and keep SuperSurf business data separate from RADIUS operational tables.

## Django And Python Web Stack

| Source | Applicable capability | Phase 0 finding |
| --- | --- | --- |
| https://www.djangoproject.com/download/ | Django versions | Django 5.2 is the current LTS line suitable for a conservative MVP; Django 6.0 is newer but not required for an LTS-first build. |
| https://docs.djangoproject.com/en/stable/ | Django official docs | Use Django auth, password hashing, sessions, CSRF, forms, admin, security middleware, and ORM rather than custom equivalents. |
| https://docs.djangoproject.com/en/stable/howto/deployment/checklist/ | Deployment checklist | Required before production activation. |
| https://www.django-rest-framework.org/ | Django REST Framework | Use sparingly for webhook endpoints and versioned APIs; keep operator UI server-rendered. |

## Data And Background Jobs

| Source | Applicable capability | Phase 0 finding |
| --- | --- | --- |
| https://www.postgresql.org/docs/current/ | PostgreSQL current docs | PostgreSQL is the source of truth for transactional payments, ledger, subscribers, audit, and RADIUS integration tables. |
| https://hub.docker.com/_/postgres | Official PostgreSQL container image | Suitable for Docker Compose development and production-like deployments after pinning. |
| https://docs.celeryq.dev/en/stable/ | Celery | Use for asynchronous payment allocation, provisioning, reports, and backups. |
| https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html | Celery Redis broker docs | Redis is a practical default broker, but Redis licensing/distribution must be reviewed in Phase 1. |
| https://redis.io/docs/latest/ | Redis docs | Candidate broker/cache. Review licence posture and consider Valkey if required. |

## Frontend And Reverse Proxy

| Source | Applicable capability | Phase 0 finding |
| --- | --- | --- |
| https://htmx.org/docs/ | HTMX | Good fit for low-JavaScript Django operator workflows. |
| https://tailwindcss.com/docs/installation | Tailwind CSS | Good fit for a restrained internal dashboard if design tokens are controlled. |
| https://alpinejs.dev/ | Alpine.js | Use only for small local interactions where HTMX and CSS are insufficient. |
| https://caddyserver.com/docs/automatic-https | Caddy automatic HTTPS | Good fit for a lightweight reverse proxy with automatic HTTPS. |
| https://hub.docker.com/_/caddy | Official Caddy container image | Candidate deployment component after pinning. |

