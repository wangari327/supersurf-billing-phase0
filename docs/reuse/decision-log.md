# Reuse Decision Log

## D001: Use Django Auth Instead Of Custom Authentication

Decision: adopt Django auth.

Reason: authentication, password hashing, sessions, CSRF integration, and permissions are mature and maintained in Django.

## D002: Use Phone Metadata Library Instead Of Custom Kenyan Parser

Decision: adopt `phonenumbers` behind `PhoneNumberNormalizer`.

Reason: Kenyan numbering metadata can change. A maintained metadata-backed library is safer than custom parsing.

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

