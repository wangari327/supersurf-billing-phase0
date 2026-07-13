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

Ordinary `LAB` without `SUPERSURF_PUBLIC_DEPLOYMENT=true` keeps local-development behavior. Public sandbox deployments use `SUPERSURF_ENVIRONMENT=LAB` plus `SUPERSURF_PUBLIC_DEPLOYMENT=true`; this keeps the visible banner labelled LAB while requiring production-style secret, PostgreSQL, host, CSRF, debug, secure-cookie, SSL-redirect, and proxy-header settings. Public LAB defaults HSTS to `0` and does not enable preload or includeSubDomains.

Container builds may set `SUPERSURF_STATICFILES_MANIFEST=true` to generate the WhiteNoise static-file manifest without turning the build environment into a public deployment. Runtime public deployments still require `SUPERSURF_PUBLIC_DEPLOYMENT=true` or `SUPERSURF_ENVIRONMENT=PRODUCTION`.

## PRODUCTION

Production requires explicit settings:

- Strong `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=false`
- PostgreSQL `DATABASE_URL`
- Real `DJANGO_ALLOWED_HOSTS`
- Real `DJANGO_CSRF_TRUSTED_ORIGINS`
- TLS at the reverse proxy
- Secure cookies
- Production-readiness checks

When `SUPERSURF_ENVIRONMENT=PRODUCTION`, Django startup fails closed if any required setting is missing, if `DJANGO_DEBUG` is not explicitly false, if the development secret is used, or if `DATABASE_URL` is absent or non-PostgreSQL. The same fail-closed checks apply to any environment with `SUPERSURF_PUBLIC_DEPLOYMENT=true`. SQLite and the local development secret are allowed only for non-public DEVELOPMENT, TEST, and LAB profiles.

Real-world values such as public domain, emails, Paybill number, Till number, KRA PIN, and licence information must remain empty until supplied by SuperSurf.
