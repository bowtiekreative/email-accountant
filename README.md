# 📬 Email Accountant

> **AI-powered email accountant** — scans your Gmail inbox for receipts, invoices, payments, and financial emails. Extracts data via OCR, categorizes as personal/business, builds a year-organized ledger, generates spending insights, and produces tax-ready reports.

## 🏗️ Architecture: scanner → Supabase (Postgres) → dashboard

The scanner/classifier is the **ingestion engine**; data lives in **Supabase**
(self-hosted Postgres + auto REST API + Studio), and the `webapp/` dashboard
reads from it. The full schema is in
`supabase/migrations/20260615000001_full_email_accountant.sql` (validated
against Postgres 16).

```bash
# 1. Stand up self-hosted Supabase (schema auto-applies on first boot)
cd supabase && cp .env.example .env   # fill in secrets — see supabase/README.md
docker compose up -d                  # Studio + API → http://localhost:8000

# 2. Point the app at it (webapp/backend env)
#    EMAIL_ACCOUNTANT_DB=supabase  SUPABASE_URL=...  SUPABASE_SERVICE_KEY=...
```

See **[supabase/README.md](supabase/README.md)** for setup and key generation.

> An alternative all-tools stack (Paperless-ngx · Akaunting · Firefly III ·
> Strapi) also exists — see [docs/STACK.md](docs/STACK.md) — but Supabase is the
> current direction.

## 🧠 Knowledge Brain

### Decision Tree: How data flows

```
Gmail Inbox
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ 1. Gmail Financial Scanner                          │
│    • Searches by query (receipt, invoice, payment)  │
│    • Downloads PDF/image attachments               │
│    • Paginates through ALL historical emails        │
└─────────────────────┬───────────────────────────────┘
                      │ raw emails + attachments
                      ▼
┌─────────────────────────────────────────────────────┐
│ 2. Receipt OCR & Extraction                         │
│    • PDF → PyMuPDF (text) or OCR fallback           │
│    • Image → Tesseract OCR                          │
│    • Regex → vendor, date, amount, line items       │
└─────────────────────┬───────────────────────────────┘
                      │ structured transaction data
                      ▼
┌─────────────────────────────────────────────────────┐
│ 3. Financial Categorization Engine                  │
│    • Rule engine: known merchant → category         │
│    • Ambiguity resolution: amount, day, keywords    │
│    • LLM fallback for edge cases                    │
│    • Personal vs Business • Income vs Expense       │
└─────────────────────┬───────────────────────────────┘
                      │ categorized transactions
                      ▼
┌─────────────────────────────────────────────────────┐
│ 4. Accounting Data Model & Ledger                   │
│    • SQLite, year-partitioned (ledger_2025.db, etc.)│
│    • Full audit trail: email → OCR → classification │
│    • Deduplication, merchant aliases, scan history  │
└──────┬──────────────────────────────┬───────────────┘
       │                              │
       ▼                              ▼
┌────────────────────┐    ┌──────────────────────────┐
│ 5. Spending Habits │    │ 6. Tax Preparation        │
│    & Analytics     │    │    System                 │
│ • Monthly reports  │    │ • IRS Schedule C mapping  │
│ • Category trends  │    │ • Deductible tracking     │
│ • Recurring detect │    │ • 50% meals auto-apply    │
│ • Budget tracking  │    │ • Year-end checklist      │
│ • HTML dashboards  │    │ • Form 1040 export        │
└────────────────────┘    └──────────────────────────┘
       │                              │
       └─────────┬────────────────────┘
                 ▼
       ┌──────────────────────────────┐
       │ 7. Hermes Cron Integration   │
       │ • Daily incremental scanning │
       │ • Monthly report generation  │
       │ • Year-end tax prep          │
       │ • Telegram notifications     │
       └──────────────────────────────┘
```

### Scenario Map

| Situation | Best Skill | What It Does |
|---|---|---|
| "I need to find all receipts in my Gmail" | `gmail-financial-scanner` | Searches Gmail by financial query patterns, paginates, downloads attachments |
| "I have a scanned receipt image" | `receipt-ocr-extraction` | OCRs the image, extracts vendor/date/amount via regex patterns |
| "Is this business or personal?" | `financial-categorization` | Rule engine checks merchant → category, heuristics for unknowns |
| "Show me my spending this month" | `spending-habits-analytics` | Monthly report with income/expense breakdown, top merchants, trends |
| "I need my deductions for tax season" | `tax-preparation-system` | Schedule C mapping, deductible tracking, year-end HTML report |
| "Set up daily email scanning" | `hermes-cron-integration` | Cron job schedule, incremental scanning, Telegram notifications |
| "What did I spend on software last year?" | `accounting-data-model` | SQL query on year ledger — category filter, export to CSV/JSON |
| "I have a receipt with both business and personal items" | `financial-categorization` | Line-item splitting: classify each product separately |
| "Scan years 2018-2024 back to inception" | `gmail-financial-scanner` | Year-by-year historical backfill with rate limiting |
| "Generate a report for my accountant" | `tax-preparation-system` | Schedule C structured export, full transaction list by category |

### People Map

| Role | What They Use | Key Reports |
|---|---|---|
| **You (Business Owner)** | Dashboard, monthly summaries, alerts | Spending trends, budget alerts, income reports |
| **Tax Accountant** | Schedule C export, year-end report | Deductible breakdown, uncategorized flags, full ledger |
| **Hermes Agent (Automation)** | Cron jobs, skills, script wrappers | Daily scans, report generation, notification delivery |

### Relationship Map

```
Gmail Scanner ──attachments──► Receipt OCR
     │                              │
     │                              ▼
     │                  Financial Categorization
     │                              │
     └───────────data──────────────►│
                                    │
                                    ▼
                          Accounting Data Model
                            │              │
                            ▼              ▼
                    Spending Habits    Tax Prep System
                            │              │
                            └──────┬───────┘
                                   ▼
                         Hermes Cron Integration
```

### Meta-Pattern: Pipeline + Partition

The **email accountant** follows a **pipeline pattern**: raw data flows unidirectionally through 7 stages, each refining the data. The **year-partition** is the key architectural decision — financial data naturally rolls up annually, and partitioning by year makes queries, exports, and migrations straightforward.

**Key pattern relationships:**
- **Predecessor → Successor**: Each skill feeds into the next. Gmail Scanner → OCR → Categorization → Ledger → Analytics & Tax
- **Data source → Consumer**: Ledger is the single source of truth consumed by both analytics and tax systems
- **Manual → Automatic**: The pipeline is designed to run continuously (cron) but has manual review gates (uncategorized flagging, high-value verification)

## 📂 Repository Structure

```
email-accountant/
├── README.md                          ← You are here
├── AGENT-PROMPT.md                    ← Full system prompt for the email accountant agent
└── skills/
    ├── gmail-financial-scanner/       ← Gmail API scanning, queries, attachment download
    ├── receipt-ocr-extraction/        ← OCR pipeline, field extraction, confidence scoring
    ├── financial-categorization/      ← Personal/business/income/expense classification
    ├── accounting-data-model/         ← SQLite schema, ledger, year partition, queries
    ├── spending-habits-analytics/     ← Monthly reports, trends, recurring detection, budgets
    ├── tax-preparation-system/        ← IRS Schedule C, deductions, year-end checklist
    └── hermes-cron-integration/       ← Automated scanning, scheduling, notifications
```

## 🚀 Quick Start

```bash
# 1. Set up Gmail API
#    - Enable Gmail API in Google Cloud Console
#    - Download credentials.json

# 2. Install dependencies
pip install google-api-python-client google-auth-oauthlib pytesseract pdf2image pillow

# 3. Initial auth (interactive, one-time)
python -c "
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file('credentials.json', ['https://www.googleapis.com/auth/gmail.readonly'])
creds = flow.run_local_server(port=0)
import pickle; pickle.dump(creds, open('token.pickle', 'wb'))
"

# 4. Schedule daily scan via Hermes
hermes cron create --schedule "0 */6 * * *" \
  --name "email-accountant" \
  --prompt "Run email accountant daily scan. Check for new financial emails. Report summary."
```

## 📋 Year-End Checklist

- [ ] Run full yearly scan (all years back to inception)
- [ ] Review all uncategorized transactions
- [ ] Verify merchant→category mappings
- [ ] Attach receipts for high-value items ($500+)
- [ ] Generate Schedule C export
- [ ] Verify totals against bank/credit card statements
- [ ] Generate HTML tax report for accountant

## 🔗 Related Repositories

- `bowtiekreative/sales-strategic-emails` — Strategic email writing skills and agent prompts
- `bowtiekreative/eventmath2026` — Timeline/event/gate/chain modelling (sister repo)