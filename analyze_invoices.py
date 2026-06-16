"""Analyze invoice emails and extract line items from bodies and attachments."""
import sys, re, json, os
sys.path.insert(0, '/opt/data/email-accountant')
from db.database import EmailAccountantDB
from datetime import datetime
from collections import defaultdict

db = EmailAccountantDB(2026)
c = db._conn

print("=" * 70)
print("INVOICE / RECEIPT ANALYSIS")
print("=" * 70)

# 1. Invoice senders
print("\n--- TOP INVOICE SENDERS ---")
senders = c.execute("""
    SELECT from_email, from_name, COUNT(*) FROM emails 
    WHERE LOWER(subject) LIKE '%invoice%' 
    GROUP BY from_email ORDER BY COUNT(*) DESC LIMIT 20
""").fetchall()
for s in senders:
    print(f"  {s[2]:3d}x | {s[0][:45]:45s} | {str(s[1] or '')[:30]}")

# 2. All unique subjects with "invoice"  
print("\n--- INVOICE SUBJECT LINES ---")
subjects = c.execute("""
    SELECT DISTINCT subject FROM emails 
    WHERE LOWER(subject) LIKE '%invoice%'
    ORDER BY subject
""").fetchall()
for s in subjects:
    print(f"  {str(s[0] or '')[:100]}")

# 3. Emails with body text that contains line items
print("\n--- PAYPAL TRANSACTIONS (all) ---")
paypal_counts = c.execute("""
    SELECT transaction_type, COUNT(*), ROUND(SUM(amount),2) 
    FROM transactions WHERE LOWER(email_from) LIKE '%paypal%'
    GROUP BY transaction_type
""").fetchall()
for t in paypal_counts:
    print(f"  {t[0]:15s} | {t[1]:4d}x | ${t[2]:>8.2f}")

# 4. Payment platforms used
print("\n--- PAYMENT PLATFORMS ---")
platforms = [
    'gofundme', 'ko-fi', 'spring', 'stripe', 'square',
    'paypal', 'waveapps', 'freshbooks', 'quickbooks', 'shopify payments',
    'fastspring', 'paddle', '2checkout', 'chargebee', 'thrivecart',
    'sendowl', 'moonclerk', 'samcart'
]
for p in platforms:
    cnt = c.execute("SELECT COUNT(*) FROM emails WHERE LOWER(from_email) LIKE ?", (f'%{p}%',)).fetchone()[0]
    txns = c.execute("SELECT COUNT(*), ROUND(SUM(amount),2) FROM transactions WHERE LOWER(email_from) LIKE ?", (f'%{p}%',)).fetchone()
    if cnt > 0:
        print(f"  {p:20s} | {cnt:4d} emails | {txns[0]:4d} txns | ${txns[1] or 0:>8.2f}")

# 5. Extract line items from email body text (simple pattern matching)
print("\n--- SAMPLE INVOICE BODY EXTRACTS ---")
# Get some invoices with body text
samples = c.execute("""
    SELECT id, from_email, subject, snippet FROM emails 
    WHERE LOWER(subject) LIKE '%invoice%' AND snippet IS NOT NULL AND snippet != ''
    LIMIT 20
""").fetchall()

for s in samples:
    print(f"\n  [#{s[0]}] {s[1][:40]} | {str(s[2] or '')[:70]}")
    text = str(s[3] or '')
    # Try to find line item patterns: description + price
    lines = text.split('\n')
    for line in lines[:10]:
        line = line.strip()
        if re.search(r'\$?\d+\.\d{2}', line):
            print(f"    ├─ {line[:120]}")

db.close()
