# Genuine Blocking Questions

These questions block production-ready implementation decisions but do not block Phase 1 foundation work unless noted.

## Required Before Payment Implementation

- What is the final subscriber account-number format?
- What are the current package names?
- What are the current package prices?
- What are renewal duration rules for each package?
- What is the grace-period policy?
- What is the partial-payment policy?
- What is the overpayment policy?
- What is the Paybill short code?
- What is the Paybill product type?
- What is the Till number?
- What is the Till product type?
- What are the Daraja sandbox credentials?
- What are the Daraja production credentials?

## Required Before RADIUS And MikroTik Implementation

- What is the desired PPPoE username format?
- May one subscriber have multiple services?
- What is the RouterOS API certificate plan?
- What is the per-NAS RADIUS shared-secret or secret-reference plan?
- Which router or CHR lab will be used for testing?
- What NAS-Identifier and NAS-IP-Address conventions should SuperSurf use?
- What plan rate-limit attributes should be generated for RouterOS?

## Required Before Production Deployment

- What is the production VPS operating system?
- What is the final public domain?
- What is the final support email?
- What is the final billing email?
- What is the final NOC email?
- What backup destination will SuperSurf use?
- What restore-time objective is acceptable?

## Current Phase 0 Handling

Until supplied:

- Leave configuration values empty.
- Mark values not configured.
- Use secure environment variables.
- Block production activation where required.
- Do not invent replacements.
