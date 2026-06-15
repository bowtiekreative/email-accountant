---
name: hermes-cron-integration
description: "Schedule automated email scanning and report generation using Hermes Agent cron jobs. Incremental scans, monthly reports, and tax prep scheduling."
domain: financial
tags:
  - cron
  - scheduling
  - automation
  - hermes
  - notifications
  - incremental
---

# Hermes Cron Integration

## Overview

Automates the email accountant system using Hermes Agent cron jobs. Schedule recurring scans (daily incremental, yearly backfill), automated report generation, and proactive alerts — all running on a VPS or local machine via Hermes.

## Architecture

```
Hermes Agent ── cron job ──► email-accountant pipeline
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
            Daily Scan     Monthly Report   Tax Prep
            (incremental)  (html report)    (year-end)
                    │             │             │
                    ▼             ▼             ▼
              Telegram/Discord → PDF → Downloads folder
```

## Setup

### 1. Install Dependencies
```bash
# On Hermes host (VPS or local):
pip install google-api-python-client google-auth-oauthlib pytesseract pdf2image pillow
apt-get install -y tesseract-ocr
```

### 2. Place Credentials
```bash
# Gmail API OAuth credentials
~/.hermes/cron/email-accountant/credentials.json
# Auth token (auto-created on first run):
~/.hermes/cron/email-accountant/token.pickle
```

### 3. Create Script Wrapper
Create `~/.hermes/scripts/email_accountant_daily.py`:

```python
#!/usr/bin/env python3
"""Run daily incremental email scan for email-accountant system."""

import sys, os, json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.expanduser('~/email-accountant'))

def main():
    days_back = int(os.environ.get('SCAN_DAYS_BACK', '3'))
    year = datetime.now().year
    
    # Run scanner
    from skills.gmail-financial-scanner.SKILL import scan_recent  # Pseudo — actual import will be from a .py module
    # In practice, implement the scanner as a Python module, then:
    # service = get_gmail_service()
    # emails = scan_recent(service, days_back=days_back)
    
    # Process new emails through OCR pipeline
    # Classify each transaction
    # Insert into ledger
    
    # Generate summary for cron output
    summary = {
        'scan_date': datetime.now().isoformat(),
        'year': year,
        'emails_scanned': 0,  # Populate from actual scan
        'new_transactions': 0,
        'status': 'success',
    }
    
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

## Cron Jobs

### 1. Daily Incremental Scan
```bash
# Schedule: every 6 hours
hermes cron create \
  --schedule "0 */6 * * *" \
  --name "email-accountant-daily" \
  --script "email_accountant_daily.py" \
  --prompt "Run the daily email accountant incremental scan. Check for new receipts, invoices, and payment confirmations. Categorize and insert into ledger for current year. Report any new transactions found." \
  --deliver "telegram"
```

### 2. Monthly Report
```bash
# Schedule: 1st of every month at 9am
hermes cron create \
  --schedule "0 9 1 * *" \
  --name "email-accountant-monthly" \
  --script "email_accountant_report.py" \
  --prompt "Generate monthly financial report HTML. Include income vs expenses, top spending categories, any flagged items, and recurring charges detected. Deliver the report file." \
  --deliver "telegram"
```

### 3. Year-End Tax Prep
```bash
# Schedule: January 15th at 10am
hermes cron create \
  --schedule "0 10 15 1 *" \
  --name "email-accountant-tax-prep" \
  --prompt "Prepare tax report for previous year. Generate Schedule C export, tax HTML report, and year-end checklist. Flag any uncategorized or un-receipted items. Deliver the report and highlight what needs user attention before filing." \
  --deliver "telegram"
```

### 4. Backfill Historical Data
```bash
# One-shot: scan years 2015-2025
# Create separate jobs per year to avoid rate limits
hermes cron create \
  --schedule "once" \
  --name "email-accountant-backfill-2025" \
  --prompt "Backfill financial data for 2025. Scan all Gmail emails from 2025 matching receipt, invoice, and payment patterns. Process through OCR, classify, and insert into ledger_2025.db. Report total transactions found and any issues." \
  --deliver "telegram"

# Repeat for each year needed
```

## Notification Templates

### Daily Scan Summary
```
📬 Email Accountant — Daily Scan
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Date: {date}
📧 New emails processed: {count}
💰 New transactions: {tx_count}
  • Income: ${income_total:.2f}
  • Expenses: ${expense_total:.2f}
⚠️ Needs review: {review_count}
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Monthly Report Summary
```
📊 Email Accountant — Monthly Report
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Period: {month} {year}
💰 Income: ${income:.2f}
💸 Expenses: ${expenses:.2f}
📈 Net: ${net:.2f}
🏷️ Top category: {top_cat} (${top_cat_amount:.2f})
⚠️ {flag_count} items need review
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Tax Prep Alert
```
📋 Email Accountant — Tax Prep Ready
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Year: {year}
💰 Income: ${income:.2f}
🧾 Deductible: ${deductible:.2f}
📈 Net Profit: ${net_profit:.2f}
⚠️ {uncategorized} uncategorized items
⚠️ {missing_receipts} missing receipts
━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 Report: tax_report_{year}.html
```

## Multi-Account Support

For scanning multiple Gmail accounts (personal + business):

```python
ACCOUNTS = {
    'personal': {
        'credentials': '~/.email-accountant/credentials_personal.json',
        'token': '~/.email-accountant/token_personal.pickle',
        'ledger_dir': '~/.email-accountant/data/personal/',
    },
    'business': {
        'credentials': '~/.email-accountant/credentials_business.json',
        'token': '~/.email-accountant/token_business.pickle',
        'ledger_dir': '~/.email-accountant/data/business/',
    },
}
```

## Concurrency & Rate Limits

| Constraint | Mitigation |
|---|---|
| Gmail API: 1 query/sec | Add 1.5s sleep between requests |
| Gmail API: 250M quota/day | Daily scan uses ~50 queries |
| Attachment download: sequential | One attachment at a time |
| OCR: CPU-bound | Tesseract uses all cores by default |
| DB writes: SQLite WAL mode | WAL allows concurrent reads during write |

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| No new transactions found | Token expired | Re-run `get_gmail_service()` with local auth |
| OCR returns garbled text | Receipt image is low quality | Try increasing contrast/threshold in preprocessing |
| Cron job crashes silently | Missing dependency | Check `cron.log` — add `pip install` step to script |
| "Message not found" error | Email deleted or moved | Set `includeSpamTrash=True` or skip that message |
| DB locked error | Concurrent write | Single cron job at a time, or upgrade to PostgreSQL |

## GOTCHAs

- **Token persistence**: OAuth token.pickle expires but auto-refreshes via refresh_token. Make sure the cron user has write access to the token file
- **Gmail API daily quota**: 1M queries/day for verified apps. Unverified apps get lower quota. Daily incrementals stay well within limits
- **First-time OAuth**: requires interactive browser flow. Run once manually on the Hermes host, then cron reuses the saved token
- **Year rollover**: January 1st the cron job needs to start writing to `ledger_{new_year}.db`. The script handles this automatically from `datetime.now().year`
- **Hermes cron context**: cron jobs run in minimal context — keep scripts self-contained with full imports
- **Delivery file limit**: Telegram caps at ~50MB. HTML reports are usually <1MB. If reports grow, compress or summarize in the notification