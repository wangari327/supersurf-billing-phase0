# M-PESA Sandbox Evidence Checklist

No M-PESA implementation may begin until this checklist is completed for each SuperSurf provider profile: Paybill sandbox, Paybill production-readiness review, Till sandbox, and Till production-readiness review as applicable.

## 2026-07-17 Paybill Sandbox Evidence

- The Daraja 3.0 sandbox C2B Register URL form rejected the attempted validation URL because the URL contained the word "MPESA".
- The portal's displayed examples used provider-neutral HTTPS confirmation and validation paths.
- Provider-neutral public callback paths under `/api/payment-callbacks/` were implemented and manually deployed in response.
- Daraja C2B Register URL returned `ResponseCode` `00000000` with `ResponseDescription` `Success`.
- One controlled Paybill simulation using `CustomerPayBillOnline`, amount `1`, and synthetic `BillRefNumber` `SS000001` produced both `c2b_validation` and `c2b_confirmation` evidence.
- The C2B events shared the same provider transaction identifier, preserved the reference and amount, used independent event-type-specific idempotency keys, and contained no result code.
- One controlled M-Pesa Express/STK Push request was accepted, and its matching `stk_result` callback reported `ResultCode` `1037` with `ResultDesc` `No response from user.`
- The observed STK callback contained no callback metadata; the absent amount, provider transaction identifier, and account reference are an observed provider payload characteristic.
- No screenshot, PDF, shortcode value, account name, callback token, credential, complete callback URL, telephone number, personal name, provider identifier value, callback-event UUID, or payload digest is recorded here.

## Product And Profile

- [x] Product type recorded: Paybill for this controlled run
- [x] Environment recorded: sandbox
- [ ] Shortcode or Till identifier recorded without inventing values
- [ ] Credential type recorded
- [ ] Credential storage or secret-reference plan reviewed
- [x] Callback base URL recorded for the environment without a token

## Callback Contract

- [x] Callback URL templates documented with a `<token>` placeholder
- [x] Exact HTTP method documented as `POST`
- [x] Observed callback payload fields documented without raw values
- [x] Required acknowledgement body documented
- [x] Required acknowledgement HTTP status documented as `200`
- [ ] Live provider duplicate callback behavior tested
- [ ] Missing-field behavior tested
- [ ] Timeout behavior tested
- [ ] Retry behavior tested
- [ ] Rate limits documented

Automated tests verify duplicate acknowledgement, idempotency, concurrent delivery handling, and immutable evidence. They are not live provider duplicate-redelivery or retry-timing evidence.

## Paybill Evidence

- [x] Account-reference field identified as `BillRefNumber`
- [ ] Account-reference empty behavior tested
- [ ] Account-reference case and separator behavior tested
- [x] C2B validation endpoint observed
- [x] C2B confirmation endpoint observed
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

## Deliberately Pending

The controlled evidence does not yet establish empty-reference behavior, reference case or separator behavior, provider retry timing, provider rate limits, live duplicate redelivery, transaction-query support, Till behavior, reversal or reconciliation behavior, production-readiness differences, provider-profile approval, or final owner approval.
