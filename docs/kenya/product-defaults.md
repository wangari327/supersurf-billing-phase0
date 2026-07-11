# Kenya Product Defaults

Fresh SuperSurf installations must start with these defaults:

| Setting | Default |
| --- | --- |
| Country | Kenya |
| ISO country code | KE |
| Currency | KES |
| Currency display label | KSh |
| Business timezone | Africa/Nairobi |
| Database timestamp storage | UTC |
| User-facing locale | en-KE |
| Default language | English |
| Date display | DD/MM/YYYY |
| Time display | 24-hour |
| Week start | Monday |
| Default telephone country code | +254 |

These values may be represented internally as settings for future expansion, but they must not block first use.

## Money Handling

- Store financial amounts as integer minor units.
- Use KES as the internal currency code.
- Display by default as `KSh 500.00`, `KSh 1,500.00`, and `KSh 25,000.00`.
- Do not use binary floating-point values for financial amounts.
- Do not hardcode VAT, withholding tax, excise duty, income tax, levy percentages, or regulatory fees.
- Tax settings must be configurable and disabled until SuperSurf explicitly configures them.
- Do not claim KRA, VAT, eTIMS, Communications Authority, or statutory compliance without separate reviewed implementation.
- Do not implement eTIMS in the MVP. Provide an extension point only.

## Business Dates

- Store database timestamps in UTC.
- Convert to Africa/Nairobi for business-day grouping, dashboard metrics, receipts, invoices, and reports.
- Daily revenue, expiries, grace boundaries, and suspension jobs must use Africa/Nairobi business dates.

## CSV Exports

- Financial amount columns must remain numeric and must not include currency symbols.
- Display exports may include a separate currency column with `KES`.
- Prevent CSV formula injection by escaping or prefixing dangerous leading characters in text fields.

