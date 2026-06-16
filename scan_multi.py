#!/usr/bin/env python3 -u
"""Multi-account Gmail scanner — uses existing GmailScanner class for proper DB storage."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db.database import EmailAccountantDB, init_sqlite
from scanner.gmail_scanner import GmailScanner
from datetime import datetime, timedelta
from pathlib import Path
import builtins
print = lambda *a, **kw: builtins.print(*a, **kw, flush=True)

def get_pwd(key):
    env = Path(__file__).parent / ".env"
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
SCAN_DAYS = 90

YEAR = datetime.now().year
init_sqlite(YEAR)

total_stored = 0
for label, email, env_key in ACCOUNTS:
    pwd = get_pwd(env_key)
    if not pwd:
        print(f"⚠️  No password for {label}")
        continue
    
    print(f"\n{'='*60}")
    print(f"SCANNING: {email} ({label})")
    print(f"{'='*60}")
    
    # Get/create account in DB
    db = EmailAccountantDB(YEAR)
    existing = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email,)).fetchone()
    if existing:
        account_id = existing['id']
    else:
        db._conn.execute("INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?,?,'gmail',1)", (label, email))
        db._conn.commit()
        account_id = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email,)).fetchone()['id']
    db.close()
    
    # Scan using GmailScanner (handles proper field mapping)
    db = EmailAccountantDB(YEAR)
    scanner = GmailScanner(db, user=email, password=pwd)
    try:
        scanner.connect()
        results = scanner.scan_and_store(
            days_back=SCAN_DAYS,
            account_id=account_id,
            account_label=label,
        )
        print(f"  ✅ Stored {len(results)} emails for {email}")
        total_stored += len(results)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scanner.disconnect()
        db.close()

print(f"\n{'='*60}")
print(f"✅ DONE: {total_stored} emails across {len(ACCOUNTS)} accounts")
print(f"{'='*60}")
