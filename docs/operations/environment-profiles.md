# Environment Profiles

Supported environment labels:

- DEVELOPMENT
- TEST
- LAB
- PRODUCTION

The current environment is displayed in the operator shell.

## DEVELOPMENT

Used for local work. May use SQLite when Docker is unavailable. Must not use production credentials.

## TEST

Used by automated tests and CI. Must not require production credentials.

## LAB

Reserved for later network and payment lab work. Lab routers and sandbox payment profiles must remain visibly separate from production.

## PRODUCTION

Production requires explicit settings:

- Strong `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=false`
- Real `DJANGO_ALLOWED_HOSTS`
- TLS at the reverse proxy
- Secure cookies
- Production-readiness checks

Real-world values such as public domain, emails, Paybill number, Till number, KRA PIN, and licence information must remain empty until supplied by SuperSurf.

