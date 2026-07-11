# Component Research And Candidate Matrix

Accessed on 2026-07-11. PyPI versions were checked with `python -m pip index versions` and PyPI JSON metadata.

## Summary Recommendation

Use mature Django/Python packages for generic infrastructure. Implement SuperSurf-specific business logic in-house, behind narrow interfaces:

- Account-number generation
- Paybill matching
- Till matching
- Unmatched-payment workflow
- Wallet allocation
- Prepaid renewal engine
- Expiry, grace, suspension, and reactivation
- Provisioning orchestration
- Network safety rules
- Kenyan ISP reports
- Bridged-DHCP-to-PPPoE migration support

## Django Foundation

| Requirement | Candidate | Source URL | Current stable version | Latest release | Licence | Python support | Django support | Suitability | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Web framework | Django | https://pypi.org/project/Django/ | 6.0.7; use 5.2.16 LTS target | 2026-07-07 | BSD-3-Clause | 6.0 requires Python >=3.12 | Official LTS support for 5.2 | Excellent | Adopt Django 5.2 LTS for Phase 1 |
| Webhook/API toolkit | Django REST Framework | https://pypi.org/project/djangorestframework/ | 3.17.1 | 2026-03-24 | BSD | Python >=3.10 | Mature Django support | Good for APIs, unnecessary for templates | Adopt only for webhooks/versioned APIs |
| Server-rendered interactivity | django-htmx | https://pypi.org/project/django-htmx/ | 1.27.0 | Registry checked | MIT/BSD-style to verify | Python >=3.10 | Django-focused | Good | Adopt |
| Filtering | django-filter | https://pypi.org/project/django-filter/ | 25.2 | Registry checked | BSD | Python >=3.10 | Django-focused | Good | Adopt |

## Authentication, RBAC, And MFA

| Requirement | Candidate | Source URL | Current stable version | Latest release | Licence | Maintenance | Suitability | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Authentication | Django auth | https://docs.djangoproject.com/en/stable/topics/auth/ | Built into Django | Current | BSD-3-Clause | Official | Excellent | Adopt unchanged |
| Object permissions | django-guardian | https://pypi.org/project/django-guardian/ | 3.3.2 | 2026-06-08 | BSD-2-Clause | Active | Good if object-level permissions are needed | Evaluate in Phase 1 |
| Predicate permissions | rules | https://pypi.org/project/rules/ | 3.5 | 2024-09-02 | MIT | Moderate | Lightweight and expressive | Evaluate against guardian |
| Role declarations | django-role-permissions | https://pypi.org/project/django-role-permissions/ | 3.2.0 | Registry checked | MIT to verify | Less clearly active than guardian | Simple role mapping | Reject for now unless Phase 1 finds a strong fit |
| TOTP backend | django-otp | https://pypi.org/project/django-otp/ | 1.7.0 | 2026-01-07 | Unlicense | Active | Good lower-level OTP foundation | Adopt behind MFA service |
| TOTP UI workflow | django-two-factor-auth | https://pypi.org/project/django-two-factor-auth/ | 1.18.1 | 2025-09-27 | MIT | Active enough | Good if built-in flows fit | Evaluate in Phase 1 |
| Login throttling | django-axes | https://pypi.org/project/django-axes/ | 8.3.1 | Registry checked | MIT | Active | Good | Adopt behind security settings |

## Audit History

| Requirement | Candidate | Source URL | Current stable version | Latest release | Licence | Suitability | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Model history | django-simple-history | https://pypi.org/project/django-simple-history/ | 3.12.0 | 2026-06-22 | BSD | Good for before/after model history | Evaluate |
| Audit log | django-auditlog | https://pypi.org/project/django-auditlog/ | 3.4.1 | 2025-12-18 | MIT | Good for automatic audit events | Evaluate |
| Versioning | django-reversion | https://pypi.org/project/django-reversion/ | Registry candidate | Registry check required in Phase 1 | BSD | More versioning than audit | Secondary candidate |

Phase 0 recommendation: use a package for generic model history, but implement SuperSurf audit policy, redaction, financial action semantics, export events, and network action events in-house.

## Money, Ledger, And Accounting

| Requirement | Candidate | Source URL | Current stable version | Latest release | Licence | Suitability | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Currency formatting | Babel | https://pypi.org/project/Babel/ | 2.18.0 | 2026-02-01 | BSD-3-Clause | Good for locale formatting | Adopt |
| Money object/fields | django-money | https://pypi.org/project/django-money/ | 3.6.1 | 2026-06-07 | BSD | Useful, but ensure integer minor-unit storage | Evaluate; may not be needed |
| Accounting suite | django-ledger | https://pypi.org/project/django-ledger/ | 0.8.4 | 2026-01-23 | Licence to verify | Too broad for ISP wallet MVP | Use as architecture reference, not dependency |
| Double-entry ledger | django-hordak | https://pypi.org/project/django-hordak/ | 2.0.0 | 2024-11-29 | MIT | More accounting-suite shape than needed | Use as reference only |
| Python accounting | python-accounting | https://pypi.org/project/python-accounting/ | 1.0.1 | Registry checked | Licence to verify | General accounting, not Django billing workflow | Reject for MVP |

Phase 0 recommendation: implement SuperSurf wallet and append-only ledger minimally in-house using integer minor units and PostgreSQL constraints. Do not adopt a full accounting suite for MVP.

## Phone Numbers

| Requirement | Candidate | Source URL | Current stable version | Latest release | Licence | Suitability | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phone metadata parsing | phonenumbers | https://pypi.org/project/phonenumbers/ | 9.0.34 | 2026-07-03 | Apache-2.0-style libphonenumber port, verify metadata | Excellent | Adopt behind `PhoneNumberNormalizer` |
| Django field/forms | django-phonenumber-field | https://pypi.org/project/django-phonenumber-field/ | 8.4.0 | 2025-11-24 | MIT | Good | Adopt if it fits form/model needs |
| Custom parser | In-house | Not applicable | Not applicable | Not applicable | Internal | Risky and unnecessary | Reject unless library fails |

## M-PESA And Daraja

| Requirement | Candidate | Source URL | Current stable version | Latest release | Licence | Maintenance | Suitability | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Daraja wrapper | django-daraja | https://pypi.org/project/django-daraja/ | 1.3.0 | 2023-05-27 | MIT | Stale for payment-critical code | Unknown current Daraja fit | Reject unless sandbox proves current compatibility |
| Daraja wrapper | python-daraja | https://pypi.org/project/python-daraja/ | 1.2.4 | 2022-04-07 | MIT | Stale | Unknown current Daraja fit | Reject |
| Daraja wrapper | mpesa-sdk | https://pypi.org/project/mpesa-sdk/ | 1.0.7 | 2020-07-22 | MIT | Very stale | Too risky | Reject |
| Thin client | httpx plus tenacity | https://pypi.org/project/httpx/ and https://pypi.org/project/tenacity/ | httpx 0.28.1; tenacity 9.1.4 | Registry checked | BSD/Apache-2.0 | Active | Strong fit | Adopt behind `MpesaProvider` |

Phase 0 recommendation: use current official Safaricom documentation, `httpx`, and `tenacity`; write thin request/response mapping and fixtures for required endpoints.

## RouterOS And RADIUS

| Requirement | Candidate | Source URL | Current stable version | Latest release | Licence | Suitability | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RouterOS API | librouteros | https://pypi.org/project/librouteros/ | 4.1.1 | 2026-06-10 | Licence metadata must be verified | Active and focused | Evaluate behind `RouterOSAdapter` |
| RouterOS API | routeros-api | https://pypi.org/project/routeros-api/ | 0.21.0 | 2025-03-07 | MIT | Mature enough to test | Evaluate behind `RouterOSAdapter` |
| RouterOS automation | Direct SSH/scripts | Official RouterOS docs | Not package | Not package | Internal | Riskier for idempotency | Reject for automated MVP writes |
| RADIUS client/CoA | pyrad | https://pypi.org/project/pyrad/ | 2.5.4 | 2026-02-05 | BSD-3-Clause | Good candidate | Evaluate for CoA/Disconnect in lab |
| Django RADIUS app | django-freeradius | https://pypi.org/project/django-freeradius/ | 0.1 | Registry checked | Unknown | Not serious candidate | Reject |
| RADIUS SQL | Official FreeRADIUS schema | https://www.freeradius.org/documentation/ | Version tied to FreeRADIUS deployment | Official | GPL project; review schema implications | Best operational boundary | Use after licence review |

## CSV, Reconciliation, Reporting

| Requirement | Candidate | Source URL | Current stable version | Licence | Suitability | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| CSV parsing | Python csv | https://docs.python.org/3/library/csv.html | Standard library | PSF | Good foundation | Adopt for statement mapping core |
| Import/export admin | django-import-export | https://pypi.org/project/django-import-export/ | 4.4.1 | BSD | Useful for admin import/export, not payment reconciliation by itself | Evaluate |
| Tabular data | tablib | https://pypi.org/project/tablib/ | 3.9.0 | MIT | Useful but not required | Evaluate |
| Dashboards | Server-rendered Django queries | Not applicable | Internal | Internal | Good for MVP | Implement minimally in-house |

## Testing And Quality

| Requirement | Candidate | Source URL | Current stable version | Latest release | Licence | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| Test runner | pytest | https://pypi.org/project/pytest/ | 9.1.1 | 2026-06-19 | MIT | Adopt |
| Django tests | pytest-django | https://pypi.org/project/pytest-django/ | 4.12.0 | Registry checked | BSD | Adopt |
| Factories | factory-boy | https://pypi.org/project/factory-boy/ | 3.3.3 | Registry checked | MIT | Adopt |
| Browser tests | Playwright | https://pypi.org/project/playwright/ | 1.61.0 | 2026-06-29 | Apache-2.0 | Adopt for critical flows |
| Linter | Ruff | https://pypi.org/project/ruff/ | 0.15.21 | 2026-07-09 | MIT | Adopt |
| Typing | mypy | https://pypi.org/project/mypy/ | 2.2.0 | Registry checked | MIT | Adopt where practical |

