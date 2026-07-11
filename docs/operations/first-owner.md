# First Owner Procedure

SuperSurf Billing does not create an automatic owner password.

## Steps

1. Apply migrations.
2. Seed roles.
3. Set a temporary local environment variable with a strong password.
4. Run `create_first_owner`.
5. Remove the environment variable.
6. Sign in and change the password if needed.

```powershell
uv run python manage.py migrate
uv run python manage.py seed_roles
$env:FIRST_OWNER_PASSWORD="replace-with-a-strong-password"
uv run python manage.py create_first_owner --username owner --email ""
Remove-Item Env:FIRST_OWNER_PASSWORD
```

Do not store the first owner password in `.env`, Compose files, shell history shared with others, screenshots, tickets, or documentation.

