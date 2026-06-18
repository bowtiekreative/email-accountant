# Deploy on Hostinger (Docker Manager — no terminal)

Hostinger's **Docker Manager → Compose** runs a single compose file; it does
**not** clone the repo, so it can't build images from source. Use
[`docker-compose.hostinger.yml`](../docker-compose.hostinger.yml), which uses
**pre-built images** (published to GHCR by GitHub Actions) and inline config —
nothing to build, no files to mount.

## One-time: publish + share the images

1. The workflow `.github/workflows/build-images.yml` builds and pushes the
   `backend` and `frontend` images to GHCR on every push to `main`
   (or run it manually: GitHub → **Actions → build-images → Run workflow**).
2. Make the two packages **public** so Hostinger can pull them without login:
   GitHub → your profile/org → **Packages** → `email-accountant-backend` →
   **Package settings → Change visibility → Public**. Repeat for
   `email-accountant-frontend`.
   *(Or, to keep them private, add your GHCR username + a token in Hostinger's
   registry settings.)*

## Generate the secrets

You need these values (generate locally or in any shell — once):

| Var | How |
|---|---|
| `POSTGRES_PASSWORD` | `openssl rand -base64 48` |
| `JWT_SECRET` | `openssl rand -base64 48` |
| `SECRET_KEY_BASE` | `openssl rand -base64 48` |
| `ANON_KEY` | JWT signed with `JWT_SECRET`, `role=anon` |
| `SERVICE_ROLE_KEY` | JWT signed with `JWT_SECRET`, `role=service_role` |

Generate `ANON_KEY` / `SERVICE_ROLE_KEY` with the official tool (paste your
`JWT_SECRET`): <https://supabase.com/docs/guides/self-hosting/docker#generate-api-keys>

## Deploy

In **Docker Manager → Compose**:

### Option A — Compose manually (recommended for a private repo)
1. Open the raw contents of `docker-compose.hostinger.yml` and **paste** it into
   the compose box.
2. In the **Environment variables** section, add (use your VPS IP or domain):

   ```env
   POSTGRES_PASSWORD=...
   JWT_SECRET=...
   SECRET_KEY_BASE=...
   ANON_KEY=...
   SERVICE_ROLE_KEY=...
   API_EXTERNAL_URL=http://YOUR_VPS_IP:8000
   SUPABASE_PUBLIC_URL=http://YOUR_VPS_IP:8000
   SITE_URL=http://YOUR_VPS_IP:3000
   WEBAPP_ORIGIN=http://YOUR_VPS_IP:3000
   ```
3. Deploy.

### Option B — Compose from URL
Point it at a reachable URL of `docker-compose.hostinger.yml` (e.g. the GitHub
**raw** URL if the repo/file is public, or a gist). Then set the same env vars.

## After it's up

- **Dashboard** → `http://YOUR_VPS_IP:3000`
- **Supabase Studio** → `http://YOUR_VPS_IP:8000`
- **API** → `http://YOUR_VPS_IP:8001`

**Open the firewall** (hPanel → VPS → Firewall) for ports **3000, 8000, 8001**.

### Apply the database schema (in the browser)
Open **Supabase Studio → SQL Editor**, paste the contents of
`supabase/migrations/20260615000001_full_email_accountant.sql`, and run it.
(This replaces the auto-init mount, which isn't available in a no-source deploy.)

## Updating later

Push to `main` → Actions rebuilds the images → in Docker Manager, **redeploy**
(or pull) the project to grab `:latest`.

## Notes

- The frontend image is **portable**: it calls `/api/*` on its own origin and
  the Next server proxies to `backend:8000` inside the compose network, so no
  VPS IP is baked into the build.
- For a clean domain + HTTPS instead of `IP:port`, put Nginx Proxy Manager or
  Caddy in front and route `/` → frontend:3000, `/api` → backend:8001,
  `/` (a subdomain) → Supabase:8000.
- The dashboard currently reads the SQLite ledger (mounted volume); wiring it to
  read live from Supabase Postgres is the next step.
