# 📬 Email Accountant — Webapp

A personal, single-user web app on top of the existing Email Accountant engine.
It does **not** rewrite the pipeline — it reuses your Python scanner, OCR,
categorization, and the SQLite ledgers (`db/database.py`) and adds a UI + API.

```
┌──────────────┐    HTTP/JSON    ┌──────────────────┐   imports    ┌────────────────┐
│  Next.js UI  │ ───────────────▶│  FastAPI backend │ ───────────▶ │ existing engine│
│ :3000        │                 │  :8000           │              │ ledgers + scan │
└──────────────┘                 └──────────────────┘              └────────────────┘
```

## Features (v1)

- **Dashboard** — income/expense/net, deductible total, monthly trend, top
  categories & merchants, filterable by year.
- **Transactions** — searchable, filterable ledger view (year / domain / type).
- **Review queue** — fix domain, type, category and deductibility on
  low-confidence or `unknown` transactions, then approve to clear them.
- **Tax** — one page, three tabs for a Canadian sole proprietor doing US
  business:
  - **CRA T2125** (CAD) — Canadian Statement of Business Activities; expenses
    map to T2125 Part 4 line numbers, meals at the 50% limit.
  - **US Schedule C** (USD) — for US-sourced business activity.
  - **GST/HST** — taxable sales and eligible-expense bases (CAD).
- **Invest & Build Wealth** — four tabs: **Net Worth** (track assets &
  liabilities, watch net worth over time, and project it forward from your
  monthly surplus), Buffett-style **advice** from your real cashflow, a
  **compound-growth** calculator, and a **financial-independence (FIRE)**
  estimator. Educational, not licensed advice.
- **Learn from edits** — when you re-categorize a merchant in the Review queue,
  the correction is saved as a rule, applied to all past transactions from that
  merchant, and used automatically on future scans.
- **Planning** — one page, four tabs:
  - **Yearly Plan** — projects the year's income/expense/net from data so far,
    and shows spending vs budget per category.
  - **Budgets** — recommends a monthly budget per category from your last 12
    months; apply individually or all at once.
  - **Subscriptions** — auto-detects recurring charges, their cadence, monthly
    cost, and active/inactive status, with a per-currency monthly burn rate.
  - **Reminders** — budget overruns, upcoming renewals, review backlog, and the
    CRA filing deadline. A daily email digest is available via cron.
- **Scans** — two buttons: **Scan recent** (fast, last few days) and
  **Full history (2006→now)** which backfills every financial email back to
  2006. Run the full scan once, then use "Scan recent" day to day. Watch
  progress and see scan history.

### Tax years

Every tax year from **2006 to the current year** is always selectable in the
dashboard and tax dropdowns, even before a year has data. Each transaction is
filed under its own email date, so reports for any historical year are correct
once the full-history scan has run. Change the earliest year with
`EMAIL_ACCOUNTANT_START_YEAR`.

### Email reminders, backups & tests

```bash
# Email the reminders digest (set SMTP_* or GMAIL_* + REMINDER_TO first).
# Add to cron for a daily nudge:  0 8 * * *  cd /path/to/repo && python reminders_cron.py
python reminders_cron.py

# Back up every ledger to ~/.email-accountant/backups/<timestamp>/
python scripts/backup_ledgers.py

# Run the test suite (currency, classifier, ledger reports, planning)
pip install pytest && python -m pytest
```

### Email accounts (Gmail + IMAP)

Manage the inboxes to scan from the **Accounts** page — Gmail or any IMAP
provider (Outlook, Yahoo, iCloud, custom). Accounts live in one shared config
(`~/.email-accountant/accounts.json`, kept out of the repo) that both scanners
read, so there's a single source of truth. Each account needs an **app
password**. The dashboard and transactions list have a **per-account filter**,
and everything still aggregates across all accounts by default.

### Currency detection

Currency is detected per email (explicit CAD/USD tokens → `.ca` sender →
known Canadian merchant → default USD), so CAD and USD transactions are
labelled correctly as they're scanned.

### Currency

CAD and USD are tracked **separately with no FX conversion** — every amount
shows in its own currency (`$` = USD, `CA$` = CAD) and totals are never added
across currencies. A currency toggle on the dashboard switches which currency
the breakdowns show; the other currency's net is always shown alongside so
nothing is hidden. At filing time, convert USD figures to CAD using
Bank of Canada rates for your CRA return.

### Categories

The ledger seeds a comprehensive taxonomy (~109 categories across personal /
business and income / expense). Business expense categories carry both an IRS
Schedule C line and a CRA T2125 line mapping, so both tax views populate
automatically. Edit the list in `db/database.py` (`SEED_SQL`) — it stays in sync
with the Supabase migration.

**How a transaction gets its category** (in `pipeline/processor.py`):
1. **Rule engine** (`classify_merchant`) — a large merchant table maps known
   senders/merchants to a specific category (matched most-specific-first), with
   sender-domain and keyword fallbacks. Granular categories are used directly
   (e.g. Starbucks → Coffee Shops, Shell → Fuel, Air Canada → Travel).
2. **Canonicalization** — every result is normalized to a name that exists in
   the taxonomy (so reports and the Review dropdown always line up).
3. **LLM fallback** (`run_llm_classify.py`) — low-confidence/unknown rows are
   sent to a local LLM, which is given the full category list from the DB and
   picks the best fit.
4. **Review queue** — anything still low-confidence is flagged for you to set by
   hand. Unknown merchants get a low-confidence guess (never a confident wrong
   answer), so they surface for review rather than hiding.

## Run it locally

Requires Python 3.11+ and Node 18+.

```bash
# 0. (Optional) pre-create a ledger file for every year 2006 → now
python db/database.py

# 1. Backend deps
cd webapp/backend
pip install -r requirements.txt
cp env.sample .env          # edit if needed (defaults work for local SQLite)

# 2. Frontend deps
cd ../frontend
npm install
cp .env.local.example .env.local

# 3. Start both (from webapp/)
cd ..
./start.sh
```

Then open <http://localhost:3000>.

To run them separately:

```bash
# backend
cd webapp/backend && python -m uvicorn app.main:app --reload --port 8000
# frontend
cd webapp/frontend && npm run dev
```

## Configuration

All via environment variables (see `backend/env.sample`):

| Var | Default | Purpose |
|---|---|---|
| `EMAIL_ACCOUNTANT_DB_DIR` | `~/.email-accountant/data` | Where the SQLite ledgers live |
| `EMAIL_ACCOUNTANT_START_YEAR` | `2006` | Earliest selectable tax year |
| `EMAIL_ACCOUNTANT_SCAN_CMD` | `python scan_daily.py` | "Scan recent" command |
| `EMAIL_ACCOUNTANT_FULL_SCAN_CMD` | `python scan_full_archive_fast.py` | "Full history" command |
| `EMAIL_ACCOUNTANT_FRONTEND_ORIGIN` | `http://localhost:3000` | CORS origin |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Where the UI finds the API |

### Going hosted later (optional)

The data layer already supports Supabase/Postgres. Set `EMAIL_ACCOUNTANT_DB=supabase`,
`SUPABASE_URL`, and `SUPABASE_SERVICE_KEY` and apply
`supabase/migrations/`. The same UI/API work unchanged.

## API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/overview?year=&currency=` | Dashboard aggregates (totals split by currency) |
| GET | `/api/currencies` | Currencies present in the ledger |
| GET | `/api/transactions?year=&domain=&type=&currency=&q=&needs_review=` | Ledger list |
| PATCH | `/api/transactions/{id}` | Edit a transaction (review) |
| GET | `/api/categories` | Category list |
| GET | `/api/reports/t2125?year=&currency=CAD` | CRA T2125 (Canada) |
| GET | `/api/reports/schedule-c?year=&currency=USD` | US Schedule C |
| GET | `/api/reports/gst-hst?year=&currency=CAD` | GST/HST summary |
| GET/POST | `/api/scans` | History / trigger a scan |
| GET | `/api/subscriptions?currency=` | Detected recurring charges |
| GET/POST/DELETE | `/api/budgets` | List / set / remove budgets |
| GET | `/api/budgets/recommendations?currency=` | Suggested budgets |
| POST | `/api/budgets/apply-recommendations?currency=` | Apply all suggestions |
| GET | `/api/plan?year=&currency=` | Yearly projection |
| GET/POST | `/api/reminders` | Preview / email the digest |
| GET | `/api/invest/advice?currency=` | Personalized wealth advice |
| POST | `/api/invest/compound` | Compound-growth calculator |
| GET | `/api/invest/fire?annual_expense=` | Financial-independence number |
| GET | `/api/learned-rules` | Rules learned from your edits |
| POST | `/api/backup` | Back up all ledgers |
| GET/POST/PATCH/DELETE | `/api/accounts` | Manage Gmail/IMAP accounts |
| GET | `/api/account-list` | Account labels for the per-account filter |
| GET/POST/DELETE | `/api/networth/accounts` | Net-worth asset/liability accounts |
| POST | `/api/networth/snapshots` | Record a balance over time |
| GET | `/api/networth/summary` | Assets, liabilities, net worth |
| GET | `/api/networth/history` | Net worth over time (chart) |
| GET | `/api/networth/projection` | Project net worth forward |

Transaction IDs are `"<ledger-file>:<rowid>"` so edits route to the correct
year-partitioned database.
