# Kenyan Subscriber Data Model

## Subscriber Identity

Required early fields:

- Account number
- Full name or business name
- Primary phone number
- Service status
- Service location
- Active subscription, if any

Optional sensitive identity fields:

- National ID number
- Passport number
- KRA PIN
- Company registration number

Sensitive identity fields must be optional, access-controlled, masked in ordinary views, excluded from ordinary exports, absent from logs and URLs, and encrypted where appropriate.

## Phone And Payer Relationships

Do not assume the payer phone number is always the subscriber phone number.

Support:

- Primary subscriber phone
- Alternate subscriber phone
- Installation contact phone
- Authorized payer numbers
- Historical payer numbers
- Support contact number

Payment matching must preserve payer identity separately from subscriber identity.

## Address And Service Site

Use fields familiar to Kenyan ISP operations:

- County
- Sub-county
- Constituency, optional
- Ward, optional
- Town
- Trading centre
- Estate
- Village or locality
- Road, optional
- Building, plot, or house identifier, optional
- Nearest landmark
- Latitude
- Longitude
- Installation directions
- Service-site notes
- Access-point notes

Do not force formal postal addresses where they are not useful.

## Account Number Options

Phase 1 should implement an owner-configurable account-number policy. Candidate formats:

- Short numeric sequence with prefix, for example `SS-000001`
- Phone-linked account reference, not equal to the phone number
- Service-site prefix plus sequence, if SuperSurf later provides site codes

Recommended default for MVP: `SS-000001` style sequence, case-insensitive during payment matching, with separators ignored for matching.

Blocking decision before production: final account-number format.

## Subscriber And Service Cardinality

Phase 0 recommendation:

- Model `Subscriber` separately from `Service`.
- Allow one subscriber to have one service in the MVP UI.
- Keep the database capable of one subscriber having multiple services later.

This avoids a migration trap if SuperSurf later serves one business or household with multiple links.

