"""Build a complete accounting ledger from all transaction data with full email provenance.

Every line item in every CSV and JSON output carries its source email ID, subject,
date, and invoice number — so you can trace any entry back to the specific email it came from.
"""
import sys, re, json, os, csv
sys.path.insert(0, '/opt/data/email-accountant')
from db.database import EmailAccountantDB
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict

OUTPUT_DIR = os.path.expanduser('~/.email-accountant/reconciliation')
os.makedirs(OUTPUT_DIR, exist_ok=True)

db = EmailAccountantDB(2026)
c = db._conn

print("BUILDING MASTER ACCOUNTING LEDGER (with full email provenance)")
print("=" * 70)

# ===================================================================
# Helper: extract invoice number from subject or body
# ===================================================================
def extract_invoice_number(subject, description, from_email):
    """Try to extract an invoice number from the data available."""
    text = f"{subject or ''} {description or ''} {from_email or ''}"
    # Try specific patterns: Invoice #N, Order #N, Receipt #N
    m = re.search(r'(?:[Ii]nvoice|#[Ii]nvoice)\s*#?\s*(\d{1,})', text)
    if m:
        return m.group(1)
    # "Payment Receipt for Invoice #N"
    m = re.search(r'(?:Payment|Order|Receipt)\s*(?:Receipt|Confirmation)?\s*(?:for|#)?\s*(?:Invoice|Order)?\s*#?\s*(\d{1,})', text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Generic "Order #12345" / "Receipt #123"
    m = re.search(r'\b(?:Order|Receipt)\s*#\s*(\d{3,})', text)
    if m:
        return m.group(1)
    return ''

# ===================================================================
# Helper: parse stored line_items JSON
# ===================================================================
def parse_line_items(raw):
    """Parse line_items stored as JSON text in the DB."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []

# ===================================================================
# 1. Income Ledger (all money received) — with source email tracking
# ===================================================================
print("\n--- INCOME LEDGER ---")
income = c.execute("""
    SELECT t.id, t.email_id, t.email_date, t.email_subject, t.merchant_name,
           t.merchant_email, t.email_from, t.amount, t.category, t.category,
           t.transaction_date, t.description, t.line_items,
           COALESCE(e.subject, '') as raw_subject
    FROM transactions t
    LEFT JOIN emails e ON e.id = t.email_id
    WHERE t.transaction_type = 'income' AND t.domain = 'business'
    ORDER BY t.email_date
""").fetchall()

income_records = []
for r in income:
    inv_num = extract_invoice_number(r['raw_subject'], r['description'], r['email_from'])
    items = parse_line_items(r['line_items'])
    income_records.append({
        'tx_id': r['id'],
        'email_id': r['email_id'],
        'email_subject': str(r['raw_subject'] or r['email_subject'] or '')[:150],
        'invoice_number': inv_num,
        'date': str(r['email_date'] or '')[:10],
        'source': str(r['merchant_email'] or r['email_from'] or '')[:50],
        'merchant': str(r['merchant_name'] or '')[:60],
        'description': str(r['description'] or '')[:200],
        'category': r['category'],
        'amount': round(r['amount'], 2),
        'line_items_count': len(items),
        'line_items': items,
    })

income_total = sum(r['amount'] for r in income_records)
print(f"  Total business income entries: {len(income_records)}")
print(f"  Total amount: ${income_total:.2f}")

# ===================================================================
# 2. Expense Ledger (all money going out - business) — with source email tracking
# ===================================================================
print("\n\n--- BUSINESS EXPENSE LEDGER ---")
expenses = c.execute("""
    SELECT t.id, t.email_id, t.email_date, t.email_subject, t.merchant_name,
           t.email_from, t.amount, t.category, t.description, t.line_items,
           COALESCE(e.subject, '') as raw_subject
    FROM transactions t
    LEFT JOIN emails e ON e.id = t.email_id
    WHERE t.transaction_type = 'expense' AND t.domain = 'business'
    ORDER BY t.email_date
""").fetchall()

expense_records = []
for r in expenses:
    inv_num = extract_invoice_number(r['raw_subject'], r['description'], r['email_from'])
    items = parse_line_items(r['line_items'])
    expense_records.append({
        'tx_id': r['id'],
        'email_id': r['email_id'],
        'email_subject': str(r['raw_subject'] or r['email_subject'] or '')[:150],
        'invoice_number': inv_num,
        'date': str(r['email_date'] or '')[:10],
        'merchant': str(r['merchant_name'] or r['email_from'] or '')[:60],
        'category': r['category'],
        'amount': round(r['amount'], 2),
        'deductible': True,
        'line_items_count': len(items),
        'line_items': items,
    })

expense_total = sum(r['amount'] for r in expense_records)
print(f"  Total business expense entries: {len(expense_records)}")
print(f"  Total deductible: ${expense_total:.2f}")

# ===================================================================
# 3. Personal Spending Tracker — with source email tracking
# ===================================================================
print("\n\n--- PERSONAL SPENDING LEDGER ---")
personal = c.execute("""
    SELECT t.id, t.email_id, t.email_date, t.email_subject, t.merchant_name,
           t.email_from, t.amount, t.category, t.description, t.line_items,
           COALESCE(e.subject, '') as raw_subject
    FROM transactions t
    LEFT JOIN emails e ON e.id = t.email_id
    WHERE t.transaction_type = 'expense' AND t.domain = 'personal'
    ORDER BY t.email_date
""").fetchall()

personal_records = []
for r in personal:
    inv_num = extract_invoice_number(r['raw_subject'], r['description'], r['email_from'])
    items = parse_line_items(r['line_items'])
    personal_records.append({
        'tx_id': r['id'],
        'email_id': r['email_id'],
        'email_subject': str(r['raw_subject'] or r['email_subject'] or '')[:150],
        'invoice_number': inv_num,
        'date': str(r['email_date'] or '')[:10],
        'merchant': str(r['merchant_name'] or r['email_from'] or '')[:60],
        'category': r['category'],
        'amount': round(r['amount'], 2),
        'line_items_count': len(items),
        'line_items': items,
    })

personal_total = sum(r['amount'] for r in personal_records)
print(f"  Total personal expense entries: {len(personal_records)}")
print(f"  Total personal spend: ${personal_total:.2f}")

# ===================================================================
# 4. Special Income (GoFundMe, Ko-fi, Spring, etc.)
# ===================================================================
print("\n\n--- SPECIAL/PLATFORM INCOME ---")
special_platforms = ['gofundme', 'ko-fi', 'spring', 'thrivecart', 'sendowl',
                     'moonclerk', 'samcart', 'fastspring', 'members.netflix']

for platform in special_platforms:
    data = c.execute("""
        SELECT COUNT(*), ROUND(SUM(t.amount),2),
               GROUP_CONCAT(DISTINCT COALESCE(t.merchant_name, t.email_from))
        FROM transactions t
        WHERE LOWER(t.email_from) LIKE ?
    """, (f'%{platform}%',)).fetchone()

    if data and data[0] > 0:
        print(f"  {platform:20s} | {data[0]:4d} txns | ${data[1] or 0:>8.2f}")

# ===================================================================
# 5. Monthly Income/Expense Summary
# ===================================================================
print("\n\n--- MONTHLY FINANCIAL SUMMARY ---")
print(f"{'Year-Month':12s} | {'Income':>10s} | {'Biz Expenses':>12s} | {'Personal':>10s} | {'Net':>10s}")
print("-" * 60)

monthly = c.execute("""
    SELECT strftime('%Y-%m', e.email_date) as ym,
           SUM(CASE WHEN t.transaction_type='income' AND t.domain='business' THEN t.amount ELSE 0 END) as income,
           SUM(CASE WHEN t.transaction_type='expense' AND t.domain='business' THEN t.amount ELSE 0 END) as biz_exp,
           SUM(CASE WHEN t.transaction_type='expense' AND t.domain='personal' THEN t.amount ELSE 0 END) as pers
    FROM transactions t
    JOIN emails e ON e.id = t.email_id
    WHERE e.email_date IS NOT NULL
    GROUP BY ym ORDER BY ym
""").fetchall()

for m in monthly[-24:]:  # Last 24 months
    ym = m['ym'] or '????'
    inc = m['income'] or 0
    biz = m['biz_exp'] or 0
    per = m['pers'] or 0
    net = inc - biz
    print(f"  {ym:12s} | ${inc:>8.2f} | ${biz:>10.2f} | ${per:>8.2f} | ${net:>8.2f}")

# ===================================================================
# 6. Write to CSV files (with full email provenance)
# ===================================================================
print("\n\n--- WRITING CSV OUTPUTS (with email provenance) ---")

# Income CSV — now includes email_id, email_subject, invoice_number, line_items
with open(os.path.join(OUTPUT_DIR, 'income_ledger.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['TxID', 'EmailID', 'EmailSubject', 'Invoice#', 'Date',
                'Source', 'Merchant', 'Description', 'Category', 'Amount',
                'LineItems'])
    for r in income_records:
        items_str = '; '.join(
            f"{li.get('description','')[:40]} (${li.get('price', li.get('amount', 0)):>.2f})"
            for li in r['line_items'][:5]
        )
        if r['line_items_count'] > 5:
            items_str += f' ... +{r["line_items_count"] - 5} more'
        w.writerow([
            r['tx_id'], r['email_id'], r['email_subject'], r['invoice_number'],
            r['date'], r['source'], r['merchant'], r['description'],
            r['category'], r['amount'], items_str,
        ])
print(f"  → Income ledger: {OUTPUT_DIR}/income_ledger.csv ({len(income_records)} rows)")

# Expenses CSV — with email provenance
with open(os.path.join(OUTPUT_DIR, 'expense_ledger.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['TxID', 'EmailID', 'EmailSubject', 'Invoice#', 'Date',
                'Merchant', 'Category', 'Amount', 'Deductible', 'LineItems'])
    for r in expense_records:
        items_str = '; '.join(
            f"{li.get('description','')[:40]} (${li.get('price', li.get('amount', 0)):>.2f})"
            for li in r['line_items'][:5]
        )
        if r['line_items_count'] > 5:
            items_str += f' ... +{r["line_items_count"] - 5} more'
        w.writerow([
            r['tx_id'], r['email_id'], r['email_subject'], r['invoice_number'],
            r['date'], r['merchant'], r['category'], r['amount'],
            r['deductible'], items_str,
        ])
print(f"  → Expense ledger: {OUTPUT_DIR}/expense_ledger.csv ({len(expense_records)} rows)")

# Personal CSV — with email provenance
with open(os.path.join(OUTPUT_DIR, 'personal_spending.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['TxID', 'EmailID', 'EmailSubject', 'Invoice#', 'Date',
                'Merchant', 'Category', 'Amount', 'LineItems'])
    for r in personal_records:
        items_str = '; '.join(
            f"{li.get('description','')[:40]} (${li.get('price', li.get('amount', 0)):>.2f})"
            for li in r['line_items'][:5]
        )
        if r['line_items_count'] > 5:
            items_str += f' ... +{r["line_items_count"] - 5} more'
        w.writerow([
            r['tx_id'], r['email_id'], r['email_subject'], r['invoice_number'],
            r['date'], r['merchant'], r['category'], r['amount'], items_str,
        ])
print(f"  → Personal spending: {OUTPUT_DIR}/personal_spending.csv ({len(personal_records)} rows)")

# ===================================================================
# 7. JSON Master Ledger (with full provenance)
# ===================================================================
master = {
    'generated_at': datetime.now().isoformat(),
    'period_covered': 'Full Gmail archive',
    'format_note': 'Every entry includes email_id and email_subject for provenance tracing',
    'summary': {
        'business_income': round(income_total, 2),
        'business_expenses': round(expense_total, 2),
        'personal_spending': round(personal_total, 2),
        'net_business': round(income_total - expense_total, 2),
        'total_transactions': len(income_records) + len(expense_records) + len(personal_records),
    },
    'income': income_records,
    'business_expenses': expense_records,
    'personal_spending': personal_records,
}

with open(os.path.join(OUTPUT_DIR, 'master_ledger.json'), 'w') as f:
    json.dump(master, f, indent=2)

# ===================================================================
# 8. Invoice Summary — dedicated file showing all invoice numbers per email
# ===================================================================
print("\n\n--- INVOICE-TO-EMAIL MAPPING ---")
all_with_invoices = [r for r in income_records + expense_records + personal_records if r['invoice_number']]
invoice_map = defaultdict(list)
for r in all_with_invoices:
    key = r['invoice_number']
    invoice_map[key].append({
        'email_id': r['email_id'],
        'email_subject': r['email_subject'],
        'tx_id': r['tx_id'],
        'date': r['date'],
        'amount': r['amount'],
        'type': 'income' if r in income_records else 'expense',
    })

invoice_summary = {
    'total_invoice_numbers_found': len(invoice_map),
    'invoices': {
        inv: {
            'invoice_number': inv,
            'source_emails': [
                {'email_id': e['email_id'],
                 'email_subject': e['email_subject'],
                 'tx_id': e['tx_id'],
                 'date': e['date'],
                 'amount': e['amount'],
                 'type': e['type']}
                for e in entries
            ],
            'total_amount': sum(e['amount'] for e in entries),
            'email_count': len(entries),
        }
        for inv, entries in sorted(invoice_map.items())
    }
}

with open(os.path.join(OUTPUT_DIR, 'invoice_email_map.json'), 'w') as f:
    json.dump(invoice_summary, f, indent=2)
print(f"  → Invoice-to-email map: {OUTPUT_DIR}/invoice_email_map.json ({len(invoice_map)} unique invoice numbers)")
print(f"  → Total entries with invoice numbers: {len(all_with_invoices)}")

# ===================================================================
# 9. Full line items detail (every individual item from transactions)
# ===================================================================
print("\n\n--- LINE ITEM DETAIL ---")
all_line_items = []
for r in income_records + expense_records + personal_records:
    for li in r['line_items']:
        all_line_items.append({
            'tx_id': r['tx_id'],
            'email_id': r['email_id'],
            'email_subject': r['email_subject'],
            'invoice_number': r['invoice_number'],
            'transaction_date': r['date'],
            'merchant': r.get('merchant', r['source']),
            'category': r['category'],
            'amount': r['amount'],
            'item_description': li.get('description', ''),
            'item_price': li.get('price', li.get('amount', 0)),
            'item_quantity': li.get('quantity', 1),
            'source_email_ref': f"Email#{r['email_id']}: {r['email_subject'][:80]}",
        })

with open(os.path.join(OUTPUT_DIR, 'line_items_detail.json'), 'w') as f:
    json.dump({
        'generated_at': datetime.now().isoformat(),
        'total_line_items': len(all_line_items),
        'line_items': all_line_items,
    }, f, indent=2)
print(f"  → Line items detail: {OUTPUT_DIR}/line_items_detail.json ({len(all_line_items)} individual items)")

# ===================================================================
# 10. Summary
# ===================================================================
print(f"\n{'=' * 70}")
print(f"✅ MASTER ACCOUNTING LEDGER — with full email provenance")
print(f"{'=' * 70}")
print(f"   Files saved to: {OUTPUT_DIR}/")
print(f"   ├─ income_ledger.csv          ({len(income_records)} rows, includes EmailID/Subject/Invoice#)")
print(f"   ├─ expense_ledger.csv         ({len(expense_records)} rows, includes EmailID/Subject/Invoice#)")
print(f"   ├─ personal_spending.csv      ({len(personal_records)} rows, includes EmailID/Subject/Invoice#)")
print(f"   ├─ master_ledger.json         (full JSON with email provenance)")
print(f"   ├─ invoice_email_map.json     ({len(invoice_map)} invoices → email mapping)")
print(f"   └─ line_items_detail.json     ({len(all_line_items)} individual line items with email provenance)")
print()
print(f"   Every CSV row now carries: TxID, EmailID, EmailSubject, Invoice#")
print(f"   → Trace ANY entry back to its exact source email instantly")

db.close()
