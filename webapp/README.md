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
- **Scans** — trigger the Gmail scan pipeline from the UI and watch progress;
  see scan history.

### Currency

CAD and USD are tracked **separately with no FX conversion** — every amount
shows in its own currency (`$` = USD, `CA$` = CAD) and totals are never added
across currencies. A currency toggle on the dashboard switches which currency
the breakdowns show; the other currency's net is always shown alongside so
nothing is hidden. At filing time, convert USD figures to CAD using
Bank of Canada rates for your CRA return.

## Run it locally

Requires Python 3.11+ and Node 18+.

```bash
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
| `EMAIL_ACCOUNTANT_SCAN_CMD` | `python scan_daily.py` | What "Scan now" runs |
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

Transaction IDs are `"<ledger-file>:<rowid>"` so edits route to the correct
year-partitioned database.
