#!/usr/bin/env python3
"""Quick multi-account scanner — fast IMAP scan, 6 broad queries, verbose output."""
import sys, os, json, imaplib, email, time, hashlib, re, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────
ACCOUNTS = [
    {
        'label': 'theapprentice4',
        'email': 'theapprentice4@gmail.com',
        'env_key': 'GMAIL_APPRENTICE_PASSWORD',
    },
    {
        'label': 'digitalstemcell',
        'email': 'digitgalstemcell@gmail.com',
        'env_key': 'GMAIL_DIGITALSTEMCELL_PASSWORD',
    },
]

def get_password_from_env(env_key):
    """Read a password from .env file by env key name."""
    env_path = Path(os.path.dirname(os.path.abspath(__file__))) / ".env"
    if not env_path.exists():
        return None
    with open(env_path) as f:
        for line in f:
            if line.startswith(env_key + '='):
                return line.split('=', 1)[1].strip().replace(' ', '')
    return None

# ── Scanner ─────────────────────────────────────────────────────────
BROAD_QUERIES = [
    ('receipt_invoice', 'OR SUBJECT "receipt" SUBJECT "invoice"'),
    ('payment', 'OR OR SUBJECT "payment" SUBJECT "paid" SUBJECT "sent"'),
    ('paypal', 'FROM "paypal.com"'),
    ('billing_sub', 'OR SUBJECT "billing" SUBJECT "subscription"'),
    ('order_confirm', 'OR SUBJECT "order" SUBJECT "confirmation"'),
    ('finance', 'OR FROM "stripe.com" FROM "squareup.com" FROM "waveapps.com" FROM "shopify.com"'),
]

ATTACHMENT_DIR = Path.home() / ".email-accountant" / "attachments"

def decode_val(val):
    if not val: return ""
    parts = decode_header(val)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            decoded.append(str(part))
    return " ".join(decoded)

def parse_email(raw_bytes):
    msg = email.message_from_bytes(raw_bytes)
    parsed = {'body_attachments': []}
    
    # Headers
    for h in ['Message-ID', 'In-Reply-To', 'References', 'From', 'To', 'Cc',
              'Reply-To', 'Subject', 'Date', 'Return-Path', 'DKIM-Signature',
              'Received-SPF', 'List-Unsubscribe', 'Content-Type']:
        val = msg.get(h, '')
        parsed[h.lower().replace('-', '_')] = decode_val(val)
    
    # Extract email addresses
    from_val = parsed.get('from', '')
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', from_val)
    parsed['from_email'] = match.group(0) if match else from_val
    parsed['from_name'] = re.sub(r'\s*<[^>]+>', '', from_val).strip(' "\'')
    
    to_val = parsed.get('to', '')
    parsed['to_emails'] = ','.join(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', to_val))
    
    # Body
    body_plain = ''
    body_html = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get('Content-Disposition', ''))
            if ct == 'text/plain' and 'attachment' not in cd:
                try:
                    body_plain += part.get_payload(decode=True).decode('utf-8', errors='replace')
                except: pass
            elif ct == 'text/html' and 'attachment' not in cd:
                try:
                    body_html += part.get_payload(decode=True).decode('utf-8', errors='replace')
                except: pass
    else:
        try:
            body_plain = msg.get_payload(decode=True).decode('utf-8', errors='replace')
        except: pass
    
    parsed['body_plain'] = body_plain
    parsed['body_html'] = body_html
    parsed['snippet'] = body_plain[:200] if body_plain else (body_html[:200] if body_html else '')
    parsed['subject'] = decode_val(msg.get('Subject', ''))
    parsed['email_date'] = decode_val(msg.get('Date', ''))
    
    return parsed

def save_attachment(att_dir, email_id, part):
    """Save an attachment and return its metadata."""
    filename = part.get_filename()
    if not filename:
        return None
    filename = decode_val(filename)
    safe_name = re.sub(r'[^\w.-]', '_', filename)
    filepath = att_dir / str(email_id) / safe_name
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    payload = part.get_payload(decode=True)
    if payload:
        with open(filepath, 'wb') as f:
            f.write(payload)
        sha256 = hashlib.sha256(payload).hexdigest()
    else:
        sha256 = ''
    
    return {
        'filename': safe_name,
        'filepath': str(filepath),
        'mime_type': part.get_content_type(),
        'size_bytes': len(payload) if payload else 0,
        'hash_sha256': sha256,
    }

def scan_account(label, email_addr, pwd):
    """Scan a single account with broad queries. Returns (email_count, error_or_none)."""
    print(f"\n{'='*60}")
    print(f"SCANNING: {email_addr} ({label})")
    print(f"{'='*60}")
    sys.stdout.flush()
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_addr, pwd)
        print(f"  ✅ IMAP login OK")
        sys.stdout.flush()
    except Exception as e:
        print(f"  ❌ IMAP login failed: {e}")
        return 0
    
    seen_ids = set()
    all_raw = []
    
    for q_name, q_pattern in BROAD_QUERIES:
        try:
            status, _ = mail.select('"[Gmail]/All Mail"')
            if status != 'OK':
                print(f"  ⚠️  Could not select All Mail folder")
                continue
            
            status, messages = mail.search(None, f'({q_pattern})')
            if status != 'OK':
                continue
            
            msg_ids = messages[0].split()
            print(f"  📨 [{q_name:18s}] {len(msg_ids)} matches")
            sys.stdout.flush()
            
            for mid in reversed(msg_ids):
                mid_str = mid.decode() if isinstance(mid, bytes) else str(mid)
                if mid_str not in seen_ids:
                    seen_ids.add(mid_str)
                    status, data = mail.fetch(mid, '(RFC822)')
                    if status == 'OK':
                        all_raw.append(data[0][1])
        except Exception as e:
            print(f"  ⚠️  Query [{q_name}] error: {e}")
    
    mail.logout()
    
    print(f"\n  📊 Total unique financial emails: {len(all_raw)}")
    sys.stdout.flush()
    
    # Now process
    from db.database import EmailAccountantDB, init_sqlite
    init_sqlite(datetime.now().year)
    db = EmailAccountantDB(datetime.now().year)
    
    # Get or create account
    existing = db._conn.execute(
        "SELECT id FROM email_accounts WHERE email_address = ?", (email_addr,)
    ).fetchone()
    if existing:
        account_id = existing['id']
    else:
        db._conn.execute(
            "INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?, ?, 'gmail', 1)",
            (label, email_addr)
        )
        db._conn.commit()
        account_id = db._conn.execute(
            "SELECT id FROM email_accounts WHERE email_address = ?", (email_addr,)
        ).fetchone()['id']
    print(f"  📋 Account DB ID: {account_id}")
    sys.stdout.flush()
    
    # Process each email
    stored = []
    for i, raw in enumerate(all_raw):
        if i > 0 and i % 50 == 0:
            print(f"     ... {i}/{len(all_raw)} processed ({len(stored)} stored)")
            sys.stdout.flush()
        
        try:
            parsed = parse_email(raw)
            attachments = parsed.pop('body_attachments', [])
            
            if account_id:
                parsed['account_id'] = account_id
            
            email_id = db.insert_email(parsed)
            
            for att in attachments:
                att_data = save_attachment(ATTACHMENT_DIR, email_id, att)
                if att_data:
                    att_data['email_id'] = email_id
                    db.insert_attachment(att_data)
            
            stored.append({
                'email_id': email_id,
                'from': parsed.get('from_email', ''),
                'subject': str(parsed.get('subject', ''))[:60],
                'date': parsed.get('email_date', ''),
            })
        except Exception as e:
            pass
    
    db.close()
    
    print(f"  ✅ Stored {len(stored)} emails in database (account_id={account_id})")
    sys.stdout.flush()
    return len(stored)

if __name__ == '__main__':
    total = 0
    for acct in ACCOUNTS:
        pwd = get_password_from_env(acct['env_key'])
        if not pwd:
            print(f"⚠️  No password for {acct['label']}. Skipping.")
            continue
        count = scan_account(acct['label'], acct['email'], pwd)
        total += count
    
    print(f"\n{'='*60}")
    print(f"✅ DONE: {total} total financial emails across all accounts")
    print(f"{'='*60}")
