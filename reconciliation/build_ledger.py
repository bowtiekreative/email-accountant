"""Build a complete accounting ledger from all transaction data, reconciling payments across platforms."""
import sys, re, json, os, csv
sys.path.insert(0, '/opt/data/email-accountant')
from db.database import EmailAccountantDB
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict

OUTPUT_DIR = os.path.expanduser('~/.email-accountant/reconciliation')
os.makedirs(OUTPUT_DIR, exist_ok=True)

db = EmailAccountantDB(2026)
c = db._conn

print("BUILDING MASTER ACCOUNTING LEDGER")
print("=" * 70)

# ===================================================================
# 1. Income Ledger (all money received)
# ===================================================================
print("\n--- INCOME LEDGER ---")
income = c.execute("""
    SELECT t.id, t.email_date, t.merchant_name, t.merchant_email, t.email_from,
           t.amount, t.category, t.transaction_date, t.description
    FROM transactions t
    WHERE t.transaction_type = 'income' AND t.domain = 'business'
    ORDER BY t.email_date
""").fetchall()

income_records = []
for r in income:
    income_records.append({
        'date': str(r['email_date'] or '')[:10],
        'source': str(r['merchant_email'] or r['email_from'] or '')[:50],
        'description': str(r['description'] or r['merchant_name'] or '')[:100],
        'category': r['category'],
        'amount': round(r['amount'], 2),
    })

income_total = sum(r['amount'] for r in income_records)
print(f"  Total business income entries: {len(income_records)}")
print(f"  Total amount: ${income_total:.2f}")

# Group by source
by_source = defaultdict(float)
for r in income_records:
    by_source[r['source']] += r['amount']
print("\n  Top income sources:")
for src, amt in sorted(by_source.items(), key=lambda x: -x[1])[:15]:
    print(f"    ${amt:>8.2f} | {src}")

# ===================================================================
# 2. Expense Ledger (all money going out - business)
# ===================================================================
print("\n\n--- BUSINESS EXPENSE LEDGER ---")
expenses = c.execute("""
    SELECT t.id, t.email_date, t.merchant_name, t.email_from,
           t.amount, t.category, t.description
    FROM transactions t
    WHERE t.transaction_type = 'expense' AND t.domain = 'business'
    ORDER BY t.email_date
""").fetchall()

expense_records = []
for r in expenses:
    expense_records.append({
        'date': str(r['email_date'] or '')[:10],
        'merchant': str(r['merchant_name'] or r['email_from'] or '')[:60],
        'category': r['category'],
        'amount': round(r['amount'], 2),
        'deductible': True,
    })

expense_total = sum(r['amount'] for r in expense_records)
print(f"  Total business expense entries: {len(expense_records)}")
print(f"  Total deductible: ${expense_total:.2f}")

# ===================================================================
# 3. Personal Spending Tracker
# ===================================================================
print("\n\n--- PERSONAL SPENDING LEDGER ---")
personal = c.execute("""
    SELECT t.id, t.email_date, t.merchant_name, t.email_from,
           t.amount, t.category, t.description
    FROM transactions t
    WHERE t.transaction_type = 'expense' AND t.domain = 'personal'
    ORDER BY t.email_date
""").fetchall()

personal_records = []
for r in personal:
    personal_records.append({
        'date': str(r['email_date'] or '')[:10],
        'merchant': str(r['merchant_name'] or r['email_from'] or '')[:60],
        'category': r['category'],
        'amount': round(r['amount'], 2),
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
# 6. Write to CSV files
# ===================================================================
print("\n\n--- WRITING CSV OUTPUTS ---")

# Income CSV
with open(os.path.join(OUTPUT_DIR, 'income_ledger.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Date', 'Source', 'Description', 'Category', 'Amount'])
    for r in income_records:
        w.writerow([r['date'], r['source'], r['description'], r['category'], r['amount']])
print(f"  → Income ledger: {OUTPUT_DIR}/income_ledger.csv ({len(income_records)} rows)")

# Expenses CSV
with open(os.path.join(OUTPUT_DIR, 'expense_ledger.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Date', 'Merchant', 'Category', 'Amount', 'Deductible'])
    for r in expense_records:
        w.writerow([r['date'], r['merchant'], r['category'], r['amount'], r['deductible']])
print(f"  → Expense ledger: {OUTPUT_DIR}/expense_ledger.csv ({len(expense_records)} rows)")

# Personal CSV
with open(os.path.join(OUTPUT_DIR, 'personal_spending.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Date', 'Merchant', 'Category', 'Amount'])
    for r in personal_records:
        w.writerow([r['date'], r['merchant'], r['category'], r['amount']])
print(f"  → Personal spending: {OUTPUT_DIR}/personal_spending.csv ({len(personal_records)} rows)")

# ===================================================================
# 7. JSON Master Ledger
# ===================================================================
master = {
    'generated_at': datetime.now().isoformat(),
    'period_covered': 'Full Gmail archive',
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

db.close()
print(f"\n✅ Master accounting system built")
print(f"   Files saved to: {OUTPUT_DIR}/")
print(f"   ├─ income_ledger.csv")
print(f"   ├─ expense_ledger.csv")
print(f"   ├─ personal_spending.csv")
print(f"   └─ master_ledger.json")
