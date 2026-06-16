#!/usr/bin/env python3 -u
"""Multi-account Gmail scanner — fast 90-day scan, then full archive in background."""
import sys, os, json, imaplib, email, time, hashlib, re, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path
import subprocess

# ── Config ─────────────────────────────────────────────────────────
ACCOUNTS = [
    ('theapprentice4', 'theapprentice4@gmail.com', 'GMAIL_APPRENTICE_PASSWORD'),
    ('digitalstemcell', 'digitalstemcell@gmail.com', 'GMAIL_DIGITALSTEMCELL_PASSWORD'),
    ('bowtiekreative', 'bowtiekreative@gmail.com', 'GMAIL_BOWTIEKREATIVE_PASSWORD'),
    ('k6rb1n', 'k6rb1n@gmail.com', 'GMAIL_K6RB1N_PASSWORD'),
]

SCAN_DAYS = 90  # Fast scan: last 90 days only

ATTACHMENT_DIR = Path.home() / ".email-accountant" / "attachments"
REPO_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = REPO_DIR / ".env"

import builtins
print = lambda *a, **kw: builtins.print(*a, **kw, flush=True)

def get_pwd(key):
    """Read password from .env."""
    if not ENV_PATH.exists():
        return None
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

# ── Scan ────────────────────────────────────────────────────────────
QUERIES = [
    'OR SUBJECT "receipt" SUBJECT "invoice"',
    'OR SUBJECT "payment" SUBJECT "paid"',
    'FROM "paypal.com"',
    'OR SUBJECT "billing" SUBJECT "subscription"',
    'OR OR SUBJECT "order" SUBJECT "confirm" FROM "stripe.com"',
]

def scan_account(label, email_addr, pwd, days=90):
    print(f"\n{'='*60}")
    print(f"SCANNING: {email_addr} ({label}) — last {days} days")
    print(f"{'='*60}")
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_addr, pwd)
        print(f"  ✅ Logged in")
    except Exception as e:
        print(f"  ❌ Login failed: {e}")
        return 0, None
    
    since = (datetime.now() - timedelta(days=days)).strftime('%d-%b-%Y')
    seen = set()
    all_raw = []
    
    for q in QUERIES:
        try:
            mail.select('"[Gmail]/All Mail"')
            status, msgs = mail.search(None, f'(SINCE {since}) {q}')
            if status != 'OK': continue
            ids = msgs[0].split()
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
    print(f"  📊 {len(all_raw)} unique financial emails (last {days}d)")
    
    # ── Store in DB ──
    from db.database import EmailAccountantDB, init_sqlite
    init_sqlite(datetime.now().year)
    db = EmailAccountantDB(datetime.now().year)
    
    existing = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()
    if existing:
        account_id = existing['id']
    else:
        db._conn.execute("INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?,?,'gmail',1)", (label, email_addr))
        db._conn.commit()
        account_id = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()['id']
    
    stored = 0
    for i, raw in enumerate(all_raw):
        if i % 100 == 0 and i > 0:
            print(f"     ... stored {stored}/{i} emails")
        try:
            parsed = parse_email(raw)
            atts = parsed.pop('body_attachments', [])
            parsed['account_id'] = account_id
            eid = db.insert_email(parsed)
            for att in atts:
                ad = save_attachment(eid, att)
                if ad:
                    ad['email_id'] = eid
                    db.insert_attachment(ad)
            stored += 1
        except:
            pass
    
    db.close()
    print(f"  ✅ Stored {stored} emails (account_id={account_id})")
    return stored, account_id

if __name__ == '__main__':
    total = 0
    for label, email, env_key in ACCOUNTS:
        pwd = get_pwd(env_key)
        if not pwd:
            print(f"⚠️  No password for {label} ({env_key})")
            continue
        count, aid = scan_account(label, email, pwd, days=SCAN_DAYS)
        total += count
    
    print(f"\n{'='*60}")
    print(f"✅ 90-DAY SCAN COMPLETE: {total} emails across {len(ACCOUNTS)} accounts")
    print(f"{'='*60}")
    print(f"\n💡 To run full archive for all accounts:")
    print(f"   python3 -u -c \"exec(open('scan_new_accounts.py').read().replace('SCAN_DAYS = 90', 'SCAN_DAYS = 365*15'))\"")
