# Self-Hosted Accounting Stack

This project's **email scanner + classifier stays the ingestion engine**; its
output is routed into mature, self-hosted tools instead of a custom UI.

```
   Gmail / IMAP inboxes
          │
          ▼
  Email scanner + OCR + classifier        ← this repo (pipeline/, scan_*.py)
          │  normalized transactions + attachments
          ▼
  Orchestrator (integrations/)            ← routes + dedups
     ├── Paperless-ngx   (:8080)  receipts/invoices → OCR + searchable archive
     ├── Akaunting       (:8010)  BUSINESS income / expenses / bills / clients
     ├── Firefly III     (:8020)  PERSONAL spending / budgets
     └── Strapi          (:1337)  glue: unified index, routing rules, sync log
```

**Routing:** `business → Akaunting`, `personal → Firefly`, attachments → Paperless.
Overridable per-domain via env (`ROUTE_*`) or Strapi **Routing Rules** at runtime.
Every routed item is recorded once in Strapi (keyed by `source_id`), so re-runs
are idempotent and you can trace any receipt across all tools.

## What each piece does

| Tool | Role | Why |
|---|---|---|
| **Paperless-ngx** | Stores + OCRs receipt/invoice PDFs & images | Searchable document archive with the original attached to each expense |
| **Akaunting** | Business bookkeeping | Real double-entry accounting, invoices, bills, vendors/clients, reports |
| **Firefly III** | Personal finance | Budgets, categories, spending insight for non-business money |
| **Strapi** | Orchestration glue | One queryable index + cross-references (Paperless doc ↔ Akaunting/Firefly entry) + routing config + sync audit log |

## One-time setup

```bash
# 1. Secrets
cp .env.stack.example .env.stack          # fill in passwords + generate secrets

# 2. Scaffold the Strapi orchestration app and inject the content-types
./strapi/init.sh

# 3. Bring the stack up
docker compose -f docker-compose.tools-stack.yml --env-file .env.stack up -d --build
```

### Configure connections from the dashboard (no env editing)

If you run the `webapp/` dashboard, open the **Connections** page to plug in
each service's URL + API token, **Test** the connection, set **routing**
(business→Akaunting / personal→Firefly), and hit **Sync now** — all from the
browser. Values are saved to `$EMAIL_ACCOUNTANT_HOME/stack_config.json` (local,
git-ignored) and the connectors read them, overriding the env vars below per
field. Env still works as a fallback if you prefer config-as-code.

Then, in each tool's UI, create an **API token** and paste it back into
`.env.stack` (or the Connections page):

| Tool | Where to get the token | Env var |
|---|---|---|
| Paperless | Settings → API / "My Profile" → token | `PAPERLESS_TOKEN` |
| Firefly III | Profile → OAuth → Personal Access Token | `FIREFLY_TOKEN` |
| Akaunting | Use admin email/password (`AKAUNTING_EMAIL`/`_PASSWORD`) or an API token | `AKAUNTING_TOKEN` |
| Strapi | Admin → Settings → API Tokens → full access | `STRAPI_TOKEN` |

In Firefly, create an **asset account** (e.g. "Checking account") and set
`FIREFLY_ASSET_ACCOUNT` to match. In Akaunting, note the company id + a bank
account id (`AKAUNTING_COMPANY_ID`, `AKAUNTING_ACCOUNT_ID`).

## Syncing the ledger into the stack

The scanner writes to the local ledger as before. Push it into the stack:

```bash
# Preview what would route (no network):
python sync_to_stack.py --dry-run

# Route everything (idempotent — Strapi dedups by source_id):
python sync_to_stack.py

# Just one year, or force a re-sync:
python sync_to_stack.py --year 2025
python sync_to_stack.py --force
```

Run it on a schedule (cron) right after the daily scan, e.g.:

```
0 */6 * * *  cd /path/to/repo && python scan_daily.py && python sync_to_stack.py
```

## Connectors (integrations/)

| File | Responsibility |
|---|---|
| `normalize.py` | Provider-neutral `NormalizedTxn`; maps a ledger row onto it |
| `paperless.py` | Upload an attachment for OCR + archive |
| `akaunting.py` | Create business income/expense; resolve/create category + contact |
| `firefly.py` | Create a personal withdrawal/deposit |
| `strapi.py` | Upsert the unified record, sync log, read routing overrides |
| `orchestrator.py` | Dedup → Paperless → route (Akaunting/Firefly) → record in Strapi |
| `config.py` | Env-driven service config + routing |

Each connector **no-ops gracefully** when its service is disabled or has no
token, so you can adopt the tools one at a time.

## Notes

- The connectors are tested with mocked HTTP (`tests/test_integrations.py`) — no
  live services needed for CI.
- The previous custom Next.js dashboard (`webapp/`) still works but is now
  **optional**; the tools' own UIs are the primary interface. Keep it if you
  want a unified read-only view, or ignore it.
- Money stays per-currency (CAD/USD) end to end — Firefly/Akaunting record the
  transaction's own `currency_code`.
