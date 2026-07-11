# Kenyan Phone Normalization

## Accepted Inputs

Accept common Kenyan mobile formats:

- `07XXXXXXXX`
- `01XXXXXXXX`
- `2547XXXXXXXX`
- `2541XXXXXXXX`
- `+2547XXXXXXXX`
- `+2541XXXXXXXX`

Normalize valid Kenyan mobile numbers to E.164:

- `+2547XXXXXXXX`
- `+2541XXXXXXXX`

Reject clearly invalid numbers.

## Implementation Decision

Use a maintained phone-number parsing library based on current numbering metadata.

Phase 1 shortlist:

- `phonenumbers`
- `django-phonenumber-field`

Wrap parsing in `PhoneNumberNormalizer` so SuperSurf business logic is not coupled directly to a package API.

## Storage

Store:

- Original user-entered value where needed for audit
- Normalized E.164 value for matching and search
- Validation status
- Source context, such as subscriber phone, payer phone, or installation contact

## Test Cases

Critical Phase 1 tests:

- `0712345678` normalizes to `+254712345678`
- `0112345678` normalizes to `+254112345678`
- `254712345678` normalizes to `+254712345678`
- `+254112345678` remains `+254112345678`
- Invalid prefixes are rejected
- Too-short and too-long values are rejected

