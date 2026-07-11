# M-PESA Sandbox Evidence Checklist

No M-PESA implementation may begin until this checklist is completed for each SuperSurf provider profile: Paybill sandbox, Paybill production-readiness review, Till sandbox, and Till production-readiness review as applicable.

## Product And Profile

- [ ] Product type recorded: Paybill or Till
- [ ] Environment recorded: sandbox or production
- [ ] Shortcode or Till identifier recorded without inventing values
- [ ] Credential type recorded
- [ ] Credential storage or secret-reference plan reviewed
- [ ] Callback base URL recorded for the environment

## Callback Contract

- [ ] Exact request URL documented
- [ ] Exact HTTP method documented
- [ ] Exact callback payload fields captured
- [ ] Required acknowledgement body documented
- [ ] Required acknowledgement HTTP status documented
- [ ] Duplicate callback behavior tested
- [ ] Missing-field behavior tested
- [ ] Timeout behavior tested
- [ ] Retry behavior tested
- [ ] Rate limits documented

## Paybill Evidence

- [ ] Account-reference field identified
- [ ] Account-reference empty behavior tested
- [ ] Account-reference case and separator behavior tested
- [ ] Validation endpoint behavior tested, if supported
- [ ] Confirmation endpoint behavior tested, if supported
- [ ] Transaction-query support tested

## Till Evidence

- [ ] Reference field support confirmed or rejected
- [ ] Payer MSISDN presence confirmed or rejected
- [ ] Behavior when MSISDN is missing tested
- [ ] Behavior when reference is missing tested
- [ ] Validation endpoint behavior tested, if supported
- [ ] Confirmation endpoint behavior tested, if supported
- [ ] Transaction-query support tested

## Reversals And Reconciliation

- [ ] Reversal representation captured
- [ ] Reversal transaction identifiers documented
- [ ] Statement export or reconciliation format captured
- [ ] Sandbox versus production differences documented
- [ ] Permitted credential types documented
- [ ] Product-specific limitations documented

## Approval Gate

- [ ] Evidence reviewed by owner
- [ ] Provider-profile configuration approved for implementation
- [ ] Remaining ambiguities documented

