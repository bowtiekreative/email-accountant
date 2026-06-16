"""Scan theapprentice4@gmail.com — full archive scan with proper processing."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import EmailAccountantDB, init_sqlite
from scanner.gmail_scanner import GmailScanner
from pipeline.processor import parse_email_financial, classify_merchant
from datetime import datetime
from pathlib import Path

EMAIL_ADDRESS = "theapprentice4@gmail.com"

def get_credential(key):
    """Read a credential directly from .env file in the repo root."""
    p = Path(os.path.dirname(os.path.abspath(__file__))) / ".env"
    if p.exists():
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    return ""

app_pwd = get_credential("GMAIL_APPRENTICE_PASSWORD").replace(" ", "")
if not app_pwd:
    app_pwd = get_credential("GMAIL_APP_PASSWORD").replace(" ", "")
if not app_pwd:
    print("❌ No password. Set GMAIL_APPRENTICE_PASSWORD in .env")
    sys.exit(1)

YEAR = datetime.now().year
print(f"{'='*60}")
print(f"SCANNING NEW ACCOUNT: {EMAIL_ADDRESS} ({YEAR})")
print(f"{'='*60}")

# 1. DB
init_sqlite(YEAR)
db = EmailAccountantDB(YEAR)

# 2. Add account
existing = db._conn.execute(
    "SELECT id FROM email_accounts WHERE email_address = ?", (EMAIL_ADDRESS,)
).fetchone()
if existing:
    account_id = existing['id']
else:
    db._conn.execute("INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?, ?, 'gmail', 1)",
                     ('theapprentice4', EMAIL_ADDRESS))
    db._conn.commit()
    account_id = db._conn.execute("SELECT id FROM email_accounts WHERE email_address = ?", (EMAIL_ADDRESS,)).fetchone()['id']
print(f"   Account ID={account_id}")

# 3. SCAN full archive
print(f"\n3. Scanning full Gmail archive (20,643 messages)...")
scanner = GmailScanner(db, user=EMAIL_ADDRESS, password=app_pwd)
try:
    scanner.connect()
    results = scanner.scan_and_store(days_back=365*15, account_id=account_id, account_label="theapprentice4")
    print(f"\n   📊 Found {len(results)} financial emails")
finally:
    scanner.disconnect()

# 4. PROCESS into transactions
print(f"\n4. Processing all new emails into transactions...")
pending = db._conn.execute(
    "SELECT id, from_email, subject, body_plain, body_html, snippet FROM emails WHERE account_id = ? AND (email_status = 'pending' OR email_status IS NULL)",
    (account_id,)
).fetchall()

tx_count = 0
for i, row in enumerate(pending):
    if i % 10 == 0:
        print(f"   {i}/{len(pending)}...", end=" ", flush=True)
    
    try:
        body = (row['body_plain'] or '') or ''
        if not body.strip():
            body = (row['body_html'] or '') or ''
        
        record = {
            'subject': row['subject'] or '',
            'body_plain': body,
            'snippet': (row['snippet'] or '')[:200],
            'from_email': row['from_email'] or '',
        }
        
        financial = parse_email_financial(record)
        if financial and financial.get('amount') and financial['amount'] > 0:
            domain, tx_type, category, confidence = classify_merchant(
                financial.get('merchant', ''), 
                row.get('subject', ''),
                financial['amount'],
                row['from_email']
            )
            
            db.insert_transaction({
                'email_id': row['id'],
                'email_from': row['from_email'],
                'email_subject': str(row['subject'] or ''),
                'email_date': None,
                'merchant_name': financial.get('merchant', '')[:100],
                'amount': financial['amount'],
                'description': financial.get('description', '')[:200],
                'domain': domain,
                'transaction_type': tx_type,
                'category': category,
                'classification_method': 'rule',
                'classification_confidence': confidence,
            })
            tx_count += 1
        
        db._conn.execute("UPDATE emails SET email_status='categorized' WHERE id=?", (row['id'],))
    except Exception as ex:
        db._conn.execute("UPDATE emails SET email_status='errored' WHERE id=?", (row['id'],))

db._conn.commit()
print(f"\n   ✅ Created {tx_count} transactions from {len(pending)} emails")

# 5. Summary
print(f"\n{'='*60}")
print(f"✅ DONE — {EMAIL_ADDRESS}")
cats = db._conn.execute("""
    SELECT COALESCE(t.category,'uncategorized') as cat, t.transaction_type,
           COUNT(*) as cnt, ROUND(SUM(ABS(t.amount)),2) as total
    FROM transactions t JOIN emails e ON e.id=t.email_id
    WHERE e.account_id=? GROUP BY t.category ORDER BY total DESC
""", (account_id,)).fetchall()
print(f"\n   Category breakdown:")
for r in cats:
    print(f"     {r['cat']:30s} | {r['transaction_type']:8s} | {r['cnt']:4d}x | ${r['total']:>8.2f}")

tot = db._conn.execute("SELECT COUNT(*) as c, ROUND(SUM(ABS(amount)),2) as t FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (account_id,)).fetchone()
print(f"\n   💰 Total: {tot['c']} txns, ${tot['t'] or 0:.2f}")

# Save report
report = {'account': EMAIL_ADDRESS,'account_id':account_id,'scanned_at':datetime.now().isoformat(),
          'emails_found':len(results),'transactions_created':tx_count,
          'categories':[dict(r) for r in cats]}
rp = Path.home() / ".email-accountant" / "scans" / "scan_theapprentice4.json"
os.makedirs(rp.parent, exist_ok=True)
with open(rp, 'w') as f: json.dump(report, f, indent=2, default=str)
print(f"\n   Report: {rp}")
db.close()
print(f"\n✅ Done!")
