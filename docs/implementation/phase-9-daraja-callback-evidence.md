# Phase 9 Daraja Callback Evidence Capture

Phase 9 adds inbound Safaricom Daraja sandbox callback receivers and append-only evidence storage. It is intentionally evidence-only: no callback creates canonical `Payment` records, Wallet credits, ledger entries, billing periods, billing charges, renewals, invoices, receipts, service activation, RADIUS rows, PPPoE credentials, RouterOS calls, or network actions.

## Routes

Callbacks are hosted on the sandbox API hostname and use an unguessable path token:

```text
/api/integrations/mpesa/<token>/c2b/validation/
/api/integrations/mpesa/<token>/c2b/confirmation/
/api/integrations/mpesa/<token>/stk/callback/
```

The configured public base URL is `MPESA_CALLBACK_BASE_URL`, defaulting to `https://sandbox-api.supersurf.co.ke`. `MPESA_CALLBACK_TOKEN` is required for public LAB deployments, must be at least 32 characters, and is compared with constant-time comparison. Incorrect or missing tokens return HTTP 404 so callback existence is not confirmed.

Each endpoint is CSRF exempt, accepts `POST` only, accepts JSON only, rejects malformed JSON with HTTP 400, rejects request bodies larger than 64 KiB with HTTP 413, returns JSON responses rather than HTML error pages, does not redirect, and does not require an authenticated browser session.

Accepted C2B validation, C2B confirmation, and STK result callbacks return:

```json
{"ResultCode": 0, "ResultDesc": "Accepted"}
```

Duplicate callbacks receive the same acknowledgement.

## Event Envelope

`billing.MpesaCallbackEvent` stores:

- UUID primary key
- `event_type`: `c2b_validation`, `c2b_confirmation`, or `stk_result`
- `payload_sha256`: lowercase canonical JSON SHA-256 digest
- unique `idempotency_key`
- `sanitized_payload`
- optional safe extracted fields: provider transaction ID, MerchantRequestID, CheckoutRequestID, account reference, amount, result code, and bounded result description
- immutable `received_at`
- immutable `created_at`

The model is append-only in application code. Model save changes, queryset updates, bulk updates, model deletes, and queryset deletes are rejected. The database enforces valid event types, unique idempotency keys, lowercase 64-character SHA-256 digests, and positive amounts when present.

## Payload Handling

The raw request body is parsed, canonicalized deterministically, hashed with SHA-256, and discarded. Only sanitized JSON and extracted safe fields are stored.

Sanitization recursively redacts sensitive values for keys containing phone, MSISDN, first name, middle name, last name, full name, account balance, organization account balance, credentials, passwords, passkeys, secrets, tokens, or authorization. Daraja `CallbackMetadata.Item` entries are also redacted when their `Name` is sensitive.

The sanitizer intentionally preserves safe provider identifiers and matching fields such as `TransID`, `MpesaReceiptNumber`, `BillRefNumber`, `AccountReference`, `MerchantRequestID`, `CheckoutRequestID`, `Amount`, `ResultCode`, `ResultDesc`, and `ResponseCode`.

The stored payload never includes request headers, cookies, client IP addresses, sessions, callback URLs, or the callback token. Logs contain only callback event UUID, event type, digest prefix, duplicate/new status, and result code where available.

## Normalization

Extraction is best-effort and never required for a syntactically valid callback to be captured. C2B payloads extract `TransID`, `TransAmount`, and `BillRefNumber` when present. STK payloads extract `MerchantRequestID`, `CheckoutRequestID`, `ResultCode`, `ResultDesc`, and nested `CallbackMetadata.Item` values such as `Amount` and `MpesaReceiptNumber`.

`ResultCode` values are evidence only. `0`, `1037`, and any other result code do not create payments, Wallet credits, or renewals in this phase.

## Idempotency

The idempotency key is deterministic:

- C2B callbacks use event type plus `TransID` when present.
- STK callbacks use event type plus `CheckoutRequestID` when present.
- All callbacks fall back to event type plus canonical payload digest.

The unique database constraint prevents duplicate evidence rows, including concurrent retries. A duplicate request returns HTTP 200, does not update or delete the original row, and logs only duplicate status without raw payload data.

## Operator Access

The read-only operator interface is:

```text
/mpesa-callbacks/
/mpesa-callbacks/<uuid:pk>/
```

The list supports event type, result code, received date filters, and search by provider transaction ID, CheckoutRequestID, MerchantRequestID, and account reference. Detail pages display extracted fields and sanitized payload JSON only.

The explicit permission is `billing.view_mpesacallbackevent`. Owner has all permissions. Administrator and Finance receive the view permission through `seed_roles`. Support, Read Only, and NOC do not receive it. No ordinary role receives add, change, or delete callback-event permissions.

## URL Command

Operators can print callback URLs from an authenticated SSH session:

```bash
cd /opt/supersurf-sandbox/current
export SUPERSURF_DEPLOYMENT_REVISION="$(cat /opt/supersurf-sandbox/shared/current-successful-sha)"
export SUPERSURF_SANDBOX_ENV_FILE="/opt/supersurf-sandbox/shared/sandbox.env"
sudo env \
  SUPERSURF_DEPLOYMENT_REVISION="$SUPERSURF_DEPLOYMENT_REVISION" \
  SUPERSURF_SANDBOX_ENV_FILE="$SUPERSURF_SANDBOX_ENV_FILE" \
  docker compose -p supersurf-sandbox -f compose.yml run --rm web \
  python manage.py show_mpesa_callback_urls
```

The command fails when the token is missing or shorter than 32 characters. It prints only the three callback URLs, not consumer keys, consumer secrets, passkeys, access tokens, or raw credentials. Because the URLs contain the token, do not paste them into normal logs, screenshots, tickets, or chat.

## Sandbox Evidence Workflow

Register the printed C2B validation and confirmation URLs in the Daraja sandbox portal. For the first controlled C2B simulator run, use `SS000001` as the Bill Reference Number. Use the printed STK callback URL in the Daraja STK simulator callback field.

After Daraja posts callbacks, inspect `/mpesa-callbacks/` as an Administrator or Finance operator. Confirm the acknowledgement response, event type, provider identifiers, account reference, amount, result code, deduplication behavior, and sanitized payload structure. Update `docs/research/mpesa-sandbox-evidence-checklist.md` with the reviewed evidence before any later payment adapter phase.
