"""Full archive scan for all secondary accounts using proven GmailScanner."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db.database import EmailAccountantDB, init_sqlite
from scanner.gmail_scanner import GmailScanner
from pipeline.processor import parse_email_financial, classify_merchant
from datetime import datetime
from pathlib import Path
import builtins
print = lambda *a, **kw: builtins.print(*a, **kw, flush=True)

def get_pwd(key):
    env = Path(os.path.dirname(os.path.abspath(__file__))) / ".env"
    if not env.exists(): return None
    with open(env) as f:
        for line in f:
            if line.startswith(key + '='):
                return line.split('=', 1)[1].strip().replace(' ', '')
    return None

ACCOUNTS = [
    ('theapprentice4', 'theapprentice4@gmail.com', 'GMAIL_APPRENTICE_PASSWORD'),
    ('digitalstemcell', 'digitalstemcell@gmail.com', 'GMAIL_DIGITALSTEMCELL_PASSWORD'),
    ('bowtiekreative', 'bowtiekreative@gmail.com', 'GMAIL_BOWTIEKREATIVE_PASSWORD'),
    ('k6rb1n', 'k6rb1n@gmail.com', 'GMAIL_K6RB1N_PASSWORD'),
    ('bnelsonblog1', 'bnelsonblog1@gmail.com', 'GMAIL_BNELSONBLOG1_PASSWORD'),
    ('hustlezontv', 'hustlezontv@gmail.com', 'GMAIL_HUSTLEZONETV_PASSWORD'),
]

YEAR = datetime.now().year

for label, email_addr, env_key in ACCOUNTS:
    pwd = get_pwd(env_key)
    if not pwd:
        print(f"⚠️  No password for {label}")
        continue
    
    print(f"\n{'='*60}")
    print(f"FULL ARCHIVE: {email_addr} ({label})")
    print(f"{'='*60}")
    
    db = EmailAccountantDB(YEAR)
    
    # Get/create account
    existing = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()
    if existing:
        account_id = existing['id']
    else:
        db._conn.execute("INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?,?,'gmail',1)", (label, email_addr))
        db._conn.commit()
        account_id = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()['id']
    
    before_emails = db._conn.execute("SELECT COUNT(*) FROM emails WHERE account_id=?", (account_id,)).fetchone()[0]
    before_txns = db._conn.execute("SELECT COUNT(*) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (account_id,)).fetchone()[0]
    print(f"  Account ID={account_id} — before: {before_emails} emails, {before_txns} txns")
    db.close()
    
    # Scan full archive using GmailScanner (proven, handles 16K+ emails)
    db = EmailAccountantDB(YEAR)
    scanner = GmailScanner(db, user=email_addr, password=pwd)
    start = time.time()
    try:
        scanner.connect()
        print(f"  ✅ Connected, scanning ALL mail...")
        results = scanner.scan_and_store(
            days_back=365*15,  # Full archive
            account_id=account_id,
            account_label=label,
        )
        elapsed = time.time() - start
        print(f"  ✅ Scan complete: {len(results)} new emails in {elapsed:.0f}s")
    except Exception as e:
        import traceback
        print(f"  ❌ Scan error: {e}")
        traceback.print_exc()
    finally:
        scanner.disconnect()
        db.close()
    
    # Process pending into transactions
    db = EmailAccountantDB(YEAR)
    c = db._conn
    pending = c.execute(
        "SELECT id, from_email, subject, body_plain, body_html, snippet, email_date FROM emails WHERE account_id=? AND (email_status='pending' OR email_status IS NULL)",
        (account_id,)
    ).fetchall()
    
    tx_count = 0
    for row in pending:
        body = (row['body_plain'] or '') or ''
        if not body.strip():
            body = (row['body_html'] or '') or ''
        record = {
            'subject': row['subject'] or '',
            'body_plain': body,
            'snippet': (row['snippet'] or '')[:200],
            'from_email': row['from_email'] or '',
        }
        try:
            financial = parse_email_financial(record)
            if financial and financial.get('amount') and float(financial['amount']) > 0:
                domain, tx_type, category, conf = classify_merchant(
                    str(financial.get('merchant', '')),
                    str(row['subject'] or ''),
                    float(financial['amount']),
                    str(row['from_email'] or ''),
                )
                db.insert_transaction({
                    'email_id': row['id'],
                    'email_from': str(row['from_email'] or ''),
                    'email_subject': str(row['subject'] or '')[:200],
                    'email_date': str(row['email_date'] or '')[:25],
                    'merchant_name': str(financial.get('merchant', ''))[:100],
                    'amount': float(financial['amount']),
                    'description': str(financial.get('description', ''))[:200],
                    'domain': domain, 'transaction_type': tx_type, 'category': category,
                    'classification_method': 'rule', 'classification_confidence': conf,
                })
                tx_count += 1
            c.execute("UPDATE emails SET email_status='categorized' WHERE id=?", (row['id'],))
        except Exception as ex:
            c.execute("UPDATE emails SET email_status='errored' WHERE id=?", (row['id'],))
    
    db._conn.commit()
    
    after_emails = c.execute("SELECT COUNT(*) FROM emails WHERE account_id=?", (account_id,)).fetchone()[0]
    after_txns = c.execute("SELECT COUNT(*) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (account_id,)).fetchone()[0]
    print(f"  ✅ {label}: +{after_emails - before_emails} emails, +{tx_count} txns (total: {after_emails} emails, {after_txns} txns)")
    db.close()

# Final summary
print(f"\n\n{'='*60}")
print(f"✅ FULL ARCHIVE COMPLETE")
print(f"{'='*60}")
db = EmailAccountantDB(YEAR)
c = db._conn
total_emails = c.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
total_txns = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
for aid in [1,2,3,4,5,6,7]:
    e = c.execute("SELECT COUNT(*) FROM emails WHERE account_id=?", (aid,)).fetchone()[0]
    t = c.execute("SELECT COUNT(*) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (aid,)).fetchone()[0]
    amt = c.execute("SELECT ROUND(SUM(ABS(amount)),2) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (aid,)).fetchone()[0]
    print(f"  Acct {aid}: {e:6d} emails, {t:5d} txns, \${amt or 0:>8.2f}")
print(f"  TOTAL:  {total_emails:6d} emails, {total_txns:5d} txns")
db.close()
