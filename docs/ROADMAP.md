# Email Accountant — Roadmap / Next Steps

The 7 **skills** in `skills/` are the design source of truth. This maps each to
what's built today, then lists the candidate next steps so you can pick.

## Where each skill stands

| Skill | Built today | Gap / opportunity |
|---|---|---|
| **gmail-financial-scanner** | IMAP scanner, multi-account (Gmail+IMAP), full-history + daily, financial queries, scan from UI, **stop** button | Never run on the real 20k yet; OAuth path optional |
| **receipt-ocr-extraction** | OCR pipeline exists (`pipeline/processor.py` PDF/Tesseract), attachments stored | OCR not surfaced in UI; line-item extraction + confidence not shown; not run at scale |
| **financial-categorization** | ~109 categories, rule engine + learned-rules + LLM fallback, **state** (paid/failed/declined/refund/scam), canonicalization | LLM step needs a model host; merchant rules grow with use |
| **accounting-data-model** | SQLite year-partitioned ledger, dedup, merchant aliases, scan history | Not yet on Supabase/Postgres; no balance/running-total view |
| **spending-habits-analytics** | Dashboard, monthly trend, top categories/merchants, **subscriptions**, **budgets + recommendations** | Recurring/anomaly detection could be deeper; saved reports |
| **tax-preparation-system** | CRA T2125 + IRS Schedule C + GST/HST views, deductible tracking, print/PDF | Not accountant-verified; no Form-1040/T1 export bundle |
| **hermes-cron-integration** | Reminders engine + `reminders_cron.py`, scheduled-scan profile, backups | Not wired to a scheduler on the VPS yet |

## Candidate next steps (pick any)

### A. Get the real data in (highest leverage)
- A1. Run a **full-history scan** on the live accounts → the 20k+ flow in with
  states/categories. Then **Reprocess all** any time rules improve.
- A2. Tune the scanner's financial queries for your real inboxes (fewer misses,
  fewer junk hits).

### B. Data correctness at scale
- B1. **Currency detection** review on real data (CAD vs USD) — sample + fix.
- B2. **Dedup** pass across accounts (same charge in 2 inboxes).
- B3. **Receipt OCR surfacing** — show extracted vendor/total/line-items + a
  confidence flag in the detail modal (uses the receipt-ocr skill at scale).

### C. UI / UX
- C1. **True email screenshot** (PNG) via a headless-render service — vs the
  current live HTML preview.
- C2. **Saved views / filters**, CSV export of the current filter.
- C3. **Bulk re-categorize** selected (not just delete).

### D. Data layer — Supabase (you have it)
- D1. Move the ledger from SQLite → **Supabase Postgres** (the schema/migration
  is ready). Dashboard reads/writes live from Postgres; multi-device.
- D2. Wire `sync_to_supabase` so scans land in Postgres directly.

### E. Strapi (you have it)
- E1. Use Strapi as the **orchestration/index** layer — one queryable record per
  transaction with cross-refs, routing rules, sync log (connectors exist in
  `integrations/`).
- E2. Or Strapi as a **headless CMS** for custom reports/dashboards over the data.

### F. Tax finishing
- F1. Accountant review of T2125 / Schedule C / GST-HST mappings.
- F2. Year-end **export bundle** (per-category ledger + receipts) for filing.

### G. Automation / hardening
- G1. Schedule the **daily scan + reminders** on the VPS (cron or the scanner
  profile) per hermes-cron.
- G2. **Auth** on the dashboard if it's ever exposed beyond Traefik.
- G3. Automated **off-box backups** of the ledger volume.

## Suggested order (if you want a default)
1. **A1** — get the 20k in and see real numbers.
2. **B1–B3** — make those numbers correct (currency, dedup, OCR).
3. **D1** — move to Supabase so it's durable/multi-device.
4. **F1** — accountant sign-off before filing.
Everything else is polish on top.
