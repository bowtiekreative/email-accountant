# Self-Hosted Supabase

Postgres + auto REST API (PostgREST) + Studio (admin UI) + Auth + Storage, in
one compose. The email-accountant schema
(`migrations/20260615000001_full_email_accountant.sql`) is **auto-applied on
first boot**.

## 1. Generate secrets

```bash
cd supabase
cp .env.example .env

# Postgres + Realtime secrets
openssl rand -base64 48      # → POSTGRES_PASSWORD
openssl rand -base64 48      # → SECRET_KEY_BASE

# JWT secret (used to sign the API keys)
openssl rand -base64 48      # → JWT_SECRET
```

Then generate the **ANON_KEY** and **SERVICE_ROLE_KEY** — they are JWTs signed
with `JWT_SECRET` carrying `role: anon` and `role: service_role`. Easiest:
use the generator at
<https://supabase.com/docs/guides/self-hosting/docker#generate-api-keys>
(paste your `JWT_SECRET`), or with the CLI:

```bash
# role=anon, exp far in the future
echo '{"role":"anon","iss":"supabase","iat":1700000000,"exp":2000000000}'      # sign with JWT_SECRET (HS256)
echo '{"role":"service_role","iss":"supabase","iat":1700000000,"exp":2000000000}'
```

Put all values into `.env`.

## 2. Start it

```bash
docker compose up -d
docker compose ps           # wait for db = healthy
```

- **Studio (admin UI):** http://localhost:8000  (or your domain)
- **API gateway:** http://localhost:8000 → `/rest/v1`, `/auth/v1`, `/storage/v1`
- **Postgres:** `localhost:5432` (user `postgres`)

Open Studio → Table editor; you should see `transactions`, `emails`,
`categories`, etc. from the migration.

## 3. Apply the schema (if not auto-applied)

Auto-apply runs only on a **fresh** volume. If you already had data, or want to
re-apply:

```bash
docker compose exec -T db psql -U postgres -d postgres \
  < migrations/20260615000001_full_email_accountant.sql
```

## 4. Point the app at Supabase

In `webapp/backend` (or the scanner) set:

```bash
EMAIL_ACCOUNTANT_DB=supabase
SUPABASE_URL=http://localhost:8000          # or your domain
SUPABASE_SERVICE_KEY=<SERVICE_ROLE_KEY>
# Direct Postgres (for the dashboard read layer):
DATABASE_URL=postgres://postgres:<POSTGRES_PASSWORD>@localhost:5432/postgres
```

The REST API is then available at `${SUPABASE_URL}/rest/v1/transactions` with
the `apikey` / `Authorization: Bearer <key>` headers — usable directly from a
Supabase client, Studio, or the dashboard.

## Production notes

- Put Kong behind a reverse proxy with TLS; set `API_EXTERNAL_URL`,
  `SUPABASE_PUBLIC_URL`, and `SITE_URL` to your `https://` domain.
- `SERVICE_ROLE_KEY` bypasses row-level security — keep it server-side only.
- Back up the `supabase_db` volume (or use `pg_dump`).
- This is a trimmed core (db, kong, auth, rest, realtime, storage, meta,
  studio). For the canonical full self-host (analytics/vector/edge-functions),
  see <https://github.com/supabase/supabase/tree/master/docker>.
