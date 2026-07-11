# Licence Review

Phase 0 did not copy third-party source code into this bundle.

## Preferred Licences

Preferred licences:

- MIT
- BSD-2-Clause
- BSD-3-Clause
- Apache-2.0
- ISC
- PostgreSQL Licence

Components under GPL, AGPL, LGPL, MPL, SSPL, Business Source Licence, source-available licences, or unclear licence metadata require explicit documented review before adoption.

## Candidate Licence Findings

| Component | Licence posture | Phase 0 finding |
| --- | --- | --- |
| Django | BSD-3-Clause | Acceptable |
| PostgreSQL | PostgreSQL Licence | Acceptable |
| psycopg 3 | LGPL with exceptions or package-specific terms to verify | Requires review but commonly used |
| djangorestframework | BSD | Acceptable |
| Celery | BSD-3-Clause | Acceptable |
| django-celery-beat | BSD | Acceptable |
| django-guardian | BSD-2-Clause | Acceptable |
| rules | MIT | Acceptable |
| django-otp | Unlicense | Usually permissive, but confirm organizational acceptance |
| django-two-factor-auth | MIT | Acceptable |
| django-simple-history | BSD | Acceptable |
| django-auditlog | MIT | Acceptable |
| django-axes | MIT | Acceptable |
| phonenumbers | libphonenumber-derived; verify Apache-2.0 posture | Likely acceptable |
| django-phonenumber-field | MIT | Acceptable |
| Babel | BSD-3-Clause | Acceptable |
| django-money | BSD | Acceptable if adopted |
| django-ledger | Licence metadata unclear in quick check | Review before dependency adoption |
| django-hordak | MIT | Acceptable but deferred |
| python-accounting | Licence metadata unclear in quick check | Reject for MVP unless reviewed |
| httpx | BSD-3-Clause | Acceptable |
| tenacity | Apache-2.0 | Acceptable |
| structlog | Apache-2.0/MIT classifiers | Acceptable after confirming chosen version |
| django-structlog | MIT | Acceptable |
| django-health-check | MIT | Acceptable |
| django-import-export | BSD | Acceptable if adopted |
| tablib | MIT | Acceptable if adopted |
| routeros-api | MIT | Acceptable if lab tests pass |
| librouteros | Licence metadata unclear in quick check | Review before adoption |
| pyrad | BSD-3-Clause | Acceptable if CoA tests pass |
| FreeRADIUS | GPL project | Integration and schema use require explicit review |
| Redis server | Licence posture changed in recent Redis history | Review Redis versus Valkey before production |
| Caddy | Apache-2.0 | Acceptable |
| Tailwind CSS | MIT | Acceptable |
| HTMX | BSD-style | Acceptable |

## Licence Process For Phase 1

Before installing production dependencies:

1. Pin exact versions in a lockfile.
2. Record package URL, source repository, version, licence, and purpose.
3. Run a dependency/licence scanner.
4. Update `THIRD_PARTY_NOTICES.md`.
5. Record any non-preferred licence in `docs/reuse/decision-log.md`.

