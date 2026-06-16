"""Full archive scan for all secondary accounts — runs as a cron job.

Scans every message in every secondary account's Gmail history, processes
transactions, and saves reports. Mirrors the full-archive approach used
for the main ryan@bowtiekreative.com account.
"""
import sys, os, json, time, imaplib, email, hashlib, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path
import builtins
print = lambda *a, **kw: builtins.print(*a, **kw, flush=True)

REPO_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = REPO_DIR / ".env"
ATTACHMENT_DIR = Path.home() / ".email-accountant" / "attachments"
YEAR = datetime.now().year

# ── All secondary accounts (excludes main ryan@ which is already fully archived) ──
ACCOUNTS = [
    ('theapprentice4', 'theapprentice4@gmail.com', 'GMAIL_APPRENTICE_PASSWORD'),
    ('digitalstemcell', 'digitalstemcell@gmail.com', 'GMAIL_DIGITALSTEMCELL_PASSWORD'),
    ('bowtiekreative', 'bowtiekreative@gmail.com', 'GMAIL_BOWTIEKREATIVE_PASSWORD'),
    ('k6rb1n', 'k6rb1n@gmail.com', 'GMAIL_K6RB1N_PASSWORD'),
    ('bnelsonblog1', 'bnelsonblog1@gmail.com', 'GMAIL_BNELSONBLOG1_PASSWORD'),
    ('hustlezonetv', 'hustlezonetv@gmail.com', 'GMAIL_HUSTLEZONETV_PASSWORD'),
]

def get_pwd(key):
    if not ENV_PATH.exists(): return None
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith(key + '='):
                return line.split('=', 1)[1].strip().replace(' ', '')
    return None

def decode_val(val):
    if not val: return ""
    parts = decode_header(val)
    r = []
    for p, e in parts:
        if isinstance(p, bytes):
            r.append(p.decode(e or 'utf-8', errors='replace'))
        else:
            r.append(str(p))
    return " ".join(r)

def parse_email(raw_bytes):
    msg = email.message_from_bytes(raw_bytes)
    parsed = {'body_attachments': []}
    for h in ['Message-ID', 'In-Reply-To', 'References', 'From', 'To', 'Cc',
              'Reply-To', 'Subject', 'Date', 'Return-Path', 'DKIM-Signature',
              'Received-SPF', 'List-Unsubscribe']:
        val = msg.get(h, '')
        parsed[h.lower().replace('-', '_')] = decode_val(val)
    from_val = parsed.get('from', '')
    m = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', from_val)
    parsed['from_email'] = m.group(0) if m else from_val
    to_val = parsed.get('to', '')
    parsed['to_emails'] = ','.join(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', to_val))
    body_plain = ''
    body_html = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get('Content-Disposition', ''))
            if ct == 'text/plain' and 'attachment' not in cd:
                try: body_plain += part.get_payload(decode=True).decode('utf-8', errors='replace')
                except: pass
            elif ct == 'text/html' and 'attachment' not in cd:
                try: body_html += part.get_payload(decode=True).decode('utf-8', errors='replace')
                except: pass
    else:
        try: body_plain = msg.get_payload(decode=True).decode('utf-8', errors='replace')
        except: pass
    parsed['body_plain'] = body_plain
    parsed['body_html'] = body_html
    parsed['snippet'] = body_plain[:200] or body_html[:200]
    parsed['subject'] = decode_val(msg.get('Subject', ''))
    parsed['email_date'] = decode_val(msg.get('Date', ''))
    return parsed

def save_attachment(email_id, part):
    fn = part.get_filename()
    if not fn: return None
    fn = decode_val(fn)
    safe = re.sub(r'[^\w.-]', '_', fn)
    fp = ATTACHMENT_DIR / str(email_id) / safe
    fp.parent.mkdir(parents=True, exist_ok=True)
    payload = part.get_payload(decode=True)
    if payload:
        with open(fp, 'wb') as f: f.write(payload)
        sha = hashlib.sha256(payload).hexdigest()
    else: sha = ''
    return {'filename': safe, 'filepath': str(fp), 'mime_type': part.get_content_type(),
            'size_bytes': len(payload) if payload else 0, 'hash_sha256': sha}

# ── Full Archive Scan ─────────────────────────────────────────────────
BROAD_QUERIES = [
    'OR SUBJECT "receipt" SUBJECT "invoice"',
    'OR SUBJECT "payment" SUBJECT "paid" OR SUBJECT "sent"',
    'OR OR OR FROM "paypal.com" FROM "stripe.com" FROM "squareup.com" FROM "waveapps.com"',
    'OR SUBJECT "billing" SUBJECT "subscription"',
    'OR OR SUBJECT "order" SUBJECT "confirm" FROM "shopify.com"',
    'OR FROM "uber.com" FROM "doordash.com"',
    'OR FROM "netflix.com" FROM "spotify.com"',
    'FROM "googleplay.com"',
    'OR FROM "openrouter.ai" FROM "anthropic.com"',
]

results_summary = {}

for label, email_addr, env_key in ACCOUNTS:
    pwd = get_pwd(env_key)
    if not pwd:
        print(f"⚠️  No password for {label}. Skipping.")
        results_summary[label] = {'error': 'no password'}
        continue
    
    print(f"\n{'='*60}")
    print(f"FULL ARCHIVE: {email_addr} ({label})")
    print(f"{'='*60}")
    
    # Connect
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_addr, pwd)
    except Exception as e:
        print(f"  ❌ Login failed: {e}")
        results_summary[label] = {'error': str(e)}
        continue
    
    # Search all mail with broad queries
    seen = set()
    all_raw = []
    for q_name, q in [(f"Q{i}", q) for i, q in enumerate(BROAD_QUERIES)]:
        try:
            mail.select('"[Gmail]/All Mail"')
            status, msgs = mail.search(None, f'({q})')
            if status != 'OK': continue
            ids = msgs[0].split()
            print(f"  📨 [{q_name}] {len(ids)} results")
            for mid in reversed(ids):
                s = mid.decode() if isinstance(mid, bytes) else str(mid)
                if s not in seen:
                    seen.add(s)
                    status, data = mail.fetch(mid, '(RFC822)')
                    if status == 'OK':
                        all_raw.append(data[0][1])
        except Exception as e:
            print(f"  ⚠️  Query error: {e}")
    
    mail.logout()
    print(f"  📊 {len(all_raw)} unique financial emails found in FULL archive")
    
    if not all_raw:
        results_summary[label] = {'total_emails': 0}
        continue
    
    # ── Store in DB ──
    from db.database import EmailAccountantDB, init_sqlite
    from pipeline.processor import parse_email_financial, classify_merchant
    init_sqlite(YEAR)
    db = EmailAccountantDB(YEAR)
    
    # Get account
    existing = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()
    if existing:
        account_id = existing['id']
    else:
        db._conn.execute("INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?,?,'gmail',1)", (label, email_addr))
        db._conn.commit()
        account_id = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()['id']
    
    # Count existing emails for this account (from 90-day scan)
    existing_count = db._conn.execute("SELECT COUNT(*) FROM emails WHERE account_id=?", (account_id,)).fetchone()[0]
    print(f"  📋 Account ID={account_id}, existing emails={existing_count}")
    
    stored = 0
    tx_count = 0
    for i, raw in enumerate(all_raw):
        if i % 100 == 0 and i > 0:
            print(f"     ... {i}/{len(all_raw)} processed ({stored} new, {tx_count} txns)")
            db._conn.commit()
        
        try:
            # Check if already in DB by message_id
            parsed = parse_email(raw)
            msg_id = parsed.get('message_id', '')
            if msg_id:
                exists = db._conn.execute("SELECT id FROM emails WHERE message_id=? AND account_id=?", (msg_id, account_id)).fetchone()
                if exists:
                    continue  # Already stored
            
            atts = parsed.pop('body_attachments', [])
            parsed['account_id'] = account_id
            eid = db.insert_email(parsed)
            
            # Save attachments
            for att in atts:
                ad = save_attachment(eid, att)
                if ad:
                    ad['email_id'] = eid
                    db.insert_attachment(ad)
            stored += 1
            
            # Process into transaction immediately
            body = (parsed.get('body_plain') or '') or ''
            if not body.strip():
                body = (parsed.get('body_html') or '') or ''
            record = {
                'subject': parsed.get('subject', ''),
                'body_plain': body,
                'snippet': (parsed.get('snippet') or '')[:200],
                'from_email': parsed.get('from_email', ''),
            }
            
            financial = parse_email_financial(record)
            if financial and financial.get('amount') and float(financial['amount']) > 0:
                domain, tx_type, category, conf = classify_merchant(
                    str(financial.get('merchant', '')),
                    str(parsed.get('subject', '')),
                    float(financial['amount']),
                    str(parsed.get('from_email', '')),
                )
                db.insert_transaction({
                    'email_id': eid,
                    'email_from': str(parsed.get('from_email', '')),
                    'email_subject': str(parsed.get('subject', ''))[:200],
                    'email_date': str(parsed.get('email_date', ''))[:25],
                    'merchant_name': str(financial.get('merchant', ''))[:100],
                    'amount': float(financial['amount']),
                    'description': str(financial.get('description', ''))[:200],
                    'domain': domain,
                    'transaction_type': tx_type,
                    'category': category,
                    'classification_method': 'rule',
                    'classification_confidence': conf,
                })
                tx_count += 1
            
            db._conn.execute("UPDATE emails SET email_status='categorized' WHERE id=?", (eid,))
        except Exception as ex:
            pass
    
    db._conn.commit()
    
    total_for_account = db._conn.execute("SELECT COUNT(*) FROM emails WHERE account_id=?", (account_id,)).fetchone()[0]
    total_tx_for_account = db._conn.execute("SELECT COUNT(*) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (account_id,)).fetchone()[0]
    total_amt = db._conn.execute("SELECT ROUND(SUM(ABS(amount)),2) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (account_id,)).fetchone()[0]
    
    db.close()
    
    print(f"\n  ✅ {label} FULL ARCHIVE COMPLETE:")
    print(f"     New emails stored: {stored}")
    print(f"     Total emails in account: {total_for_account}")
    print(f"     Total transactions: {total_tx_for_account}")
    print(f"     Total value: ${total_amt or 0:.2f}")
    
    results_summary[label] = {
        'email': email_addr,
        'new_emails': stored,
        'total_emails': total_for_account,
        'new_transactions': tx_count,
        'total_transactions': total_tx_for_account,
        'total_value': round(total_amt or 0, 2),
    }

# ── Final Report ──────────────────────────────────────────────────────
print(f"\n\n{'='*60}")
print(f"✅ FULL ARCHIVE COMPLETE — ALL ACCOUNTS")
print(f"{'='*60}")
print(f"{'Account':20s} | {'New Emails':>10s} | {'Total Emails':>12s} | {'New Txns':>8s} | {'Total Txns':>10s} | {'Total Value':>11s}")
print("-" * 80)
total_emails = 0
total_txns = 0
total_value = 0.0
for label, info in results_summary.items():
    ne = info.get('new_emails', 0)
    te = info.get('total_emails', 0)
    nt = info.get('new_transactions', 0)
    tt = info.get('total_transactions', 0)
    tv = info.get('total_value', 0)
    print(f"  {label:18s} | {ne:>8d}   | {te:>10d}    | {nt:>6d}   | {tt:>8d}    | ${tv:>8.2f}")
    total_emails += te
    total_txns += tt
    total_value += tv

print("-" * 80)
print(f"  {'TOTAL':18s} | {'':>8s}   | {total_emails:>10d}    | {'':>6s}   | {total_txns:>8d}    | ${total_value:>8.2f}")

# Save report
report_path = Path.home() / ".email-accountant" / "scans" / f"full_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
os.makedirs(report_path.parent, exist_ok=True)
with open(report_path, 'w') as f:
    json.dump({
        'completed_at': datetime.now().isoformat(),
        'accounts': results_summary,
    }, f, indent=2, default=str)

print(f"\n📄 Report saved: {report_path}")
print(f"\nDone!")
