#!/usr/bin/env python3
"""Quick scan hustlezonetv only."""
import sys, os, json, time, imaplib, email, hashlib, re
sys.path.insert(0, '/opt/data/email-accountant')
from datetime import datetime
from email.header import decode_header
from pathlib import Path

ENV_PATH = Path('/opt/data/email-accountant/.env')
ATTACHMENT_DIR = Path.home() / ".email-accountant" / "attachments"
YEAR = 2026
BATCH_SIZE = 100

ACCOUNT = ('hustlezonetv', 'hustlezonetv@gmail.com', 'GMAIL_HUSTLEZONETV_PASSWORD')

FINANCIAL_QUERIES = [
    'SUBJECT "receipt"', 'SUBJECT "invoice"', 'SUBJECT "payment"',
    'SUBJECT "billing"', 'SUBJECT "subscription"', 'SUBJECT "order confirmation"',
    'SUBJECT "your receipt"', 'SUBJECT "payment received"', 'SUBJECT "payment to"',
    'SUBJECT "you sent"', 'SUBJECT "paid"', 'SUBJECT "declined"',
    'SUBJECT "transaction"', 'SUBJECT "purchase"', 'SUBJECT "charge"',
    'SUBJECT "refund"', 'FROM "paypal.com"', 'FROM "stripe.com"',
    'FROM "squareup.com"', 'FROM "shopify.com"', 'FROM "waveapps.com"',
    'FROM "uber.com"', 'FROM "doordash.com"', 'FROM "netflix.com"',
    'FROM "spotify.com"', 'FROM "googleplay.com"', 'FROM "openrouter.ai"',
    'FROM "anthropic.com"',
]

def get_pwd(key):
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
    hdr_map = {
        'Message-ID': 'message_id', 'In-Reply-To': 'in_reply_to',
        'References': 'references_header', 'From': 'from_header',
        'To': 'to_header', 'Cc': 'cc_header', 'Reply-To': 'reply_to',
        'Subject': 'subject', 'Date': 'email_date', 'Return-Path': 'return_path',
        'DKIM-Signature': 'dkim_signature', 'Received-SPF': 'spf_status',
        'List-Unsubscribe': 'list_unsubscribe',
    }
    for hdr, key in hdr_map.items():
        parsed[key] = decode_val(msg.get(hdr, ''))
    from_val = parsed.get('from_header', '')
    m = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', from_val)
    parsed['from_email'] = m.group(0) if m else from_val
    to_val = parsed.get('to_header', '') or ''
    parsed['to_emails'] = json.dumps(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', to_val))
    cc_val = parsed.get('cc_header', '') or ''
    parsed['cc_emails'] = json.dumps(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', cc_val))
    body_plain = ''
    body_html = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get('Content-Disposition', ''))
            fn = part.get_filename()
            if fn:
                parsed['body_attachments'].append(part)
            elif ct == 'text/plain' and 'attachment' not in cd:
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
    parsed['snippet'] = (body_plain or body_html or '')[:200]
    return parsed

label, email_addr, env_key = ACCOUNT
pwd = get_pwd(env_key)
if not pwd:
    print("❌ No password!")
    sys.exit(1)

print(f"📧 FULL ARCHIVE: {email_addr} ({label})")
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(email_addr, pwd)
mail.select('"[Gmail]/All Mail"')
print("✅ Connected")

# Phase 1: Collect IDs
all_ids = set()
for i, query in enumerate(FINANCIAL_QUERIES):
    try:
        status, msgs = mail.search(None, f'({query})')
        if status != 'OK': continue
        ids = set(msgs[0].split())
        n_old = len(all_ids)
        all_ids |= ids
        print(f"  📨 Q{i:2d}: {len(ids):>5d} results (+{len(all_ids)-n_old} new)")
        time.sleep(0.3)
    except Exception as e:
        print(f"  ⚠️  Q{i} error: {e}")

print(f"\n📊 Total unique: {len(all_ids)}")

# Phase 2: Batch-fetch
all_raw = []
sorted_ids = sorted(all_ids, key=lambda x: int(x))
for batch_start in range(0, len(sorted_ids), BATCH_SIZE):
    batch = sorted_ids[batch_start:batch_start + BATCH_SIZE]
    id_str = ','.join(x.decode() if isinstance(x, bytes) else str(x) for x in batch)
    try:
        status, data = mail.fetch(id_str, '(RFC822)')
        if status == 'OK':
            for i in range(0, len(data), 2):
                if data[i] and isinstance(data[i], tuple):
                    all_raw.append(data[i][1])
    except:
        for mid in batch:
            try:
                st, d = mail.fetch(mid, '(RFC822)')
                if st == 'OK' and d[0]: all_raw.append(d[0][1])
            except: pass
    if (batch_start // BATCH_SIZE) % 5 == 0 and batch_start > 0:
        print(f"     ... fetched {batch_start}/{len(sorted_ids)}")

mail.logout()
print(f"✅ Fetched {len(all_raw)} messages")

# Phase 3: Store
from db.database import EmailAccountantDB, init_sqlite
init_sqlite(YEAR)
db = EmailAccountantDB(YEAR)

row = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()
account_id = row['id'] if row else None
if not account_id:
    db._conn.execute("INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?,?,'gmail',1)", (label, email_addr))
    db._conn.commit()
    account_id = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()['id']

existing_before = db._conn.execute("SELECT COUNT(*) FROM emails WHERE account_id=?", (account_id,)).fetchone()[0]
print(f"Account ID={account_id}, existing={existing_before}")

from pipeline.processor import parse_email_financial, classify_merchant
stored = 0; tx_count = 0; skipped = 0

for i, raw in enumerate(all_raw):
    if i % 200 == 0 and i > 0:
        db._conn.commit()
        print(f"  ... {i}/{len(all_raw)} ({stored} new, {tx_count} txns, {skipped} dupes)")
    try:
        parsed = parse_email(raw)
        msg_id = parsed.get('message_id', '') or ''
        if msg_id:
            r2 = db._conn.execute("SELECT id FROM emails WHERE message_id=? AND account_id=?", (msg_id, account_id)).fetchone()
            if r2:
                skipped += 1
                continue
        atts = parsed.pop('body_attachments', [])
        parsed['account_id'] = account_id
        eid = db.insert_email(parsed)
        for att in atts[:5]:
            ad = None
            fn = att.get_filename()
            if fn:
                fn = decode_val(fn)
                safe = re.sub(r'[^\w.-]', '_', fn)
                fp = ATTACHMENT_DIR / str(eid) / safe
                fp.parent.mkdir(parents=True, exist_ok=True)
                payload = att.get_payload(decode=True)
                if payload:
                    with open(fp, 'wb') as f: f.write(payload)
                    ad = {'filename': safe, 'filepath': str(fp), 'mime_type': att.get_content_type(),
                          'size_bytes': len(payload), 'hash_sha256': hashlib.sha256(payload).hexdigest()}
            if ad:
                ad['email_id'] = eid
                db.insert_attachment(ad)
        stored += 1

        body = (parsed.get('body_plain') or '') or ''
        if not body.strip():
            body = (parsed.get('body_html') or '') or ''
        record = {'subject': parsed.get('subject', '') or '', 'body_plain': body or '',
                  'snippet': (parsed.get('snippet') or '')[:200], 'from_email': parsed.get('from_email', '') or ''}
        financial = parse_email_financial(record)
        if financial and financial.get('amount'):
            try:
                amt = float(financial['amount'])
                if amt > 0:
                    merchant = str(financial.get('merchant', '') or '')
                    domain, tx_type, category, conf = classify_merchant(
                        merchant or (parsed.get('from_email', '') or ''),
                        str(parsed.get('subject', '') or ''), amt,
                        str(parsed.get('from_email', '') or ''),
                    )
                    db.insert_transaction({'email_id': eid, 'account_id': account_id,
                        'email_from': str(parsed.get('from_email', '') or ''),
                        'email_subject': str(parsed.get('subject', '') or '')[:200],
                        'email_date': str(parsed.get('email_date', '') or '')[:25],
                        'merchant_name': merchant[:100], 'amount': amt,
                        'description': str(parsed.get('subject', '') or '')[:200],
                        'domain': domain, 'transaction_type': tx_type, 'category': category,
                        'classification_method': 'rule', 'classification_confidence': conf})
                    tx_count += 1
            except: pass
        db._conn.execute("UPDATE emails SET email_status='categorized' WHERE id=?", (eid,))
    except: pass

db._conn.commit()

total_after = db._conn.execute("SELECT COUNT(*) FROM emails WHERE account_id=?", (account_id,)).fetchone()[0]
total_tx = db._conn.execute("SELECT COUNT(*) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (account_id,)).fetchone()[0]
total_val = db._conn.execute("SELECT ROUND(SUM(ABS(amount)),2) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?", (account_id,)).fetchone()[0]

print(f"\n✅ hustlezonetv DONE:")
print(f"   New emails: {stored}")
print(f"   Total emails: {total_after}")
print(f"   Total txns: {total_tx}")
print(f"   Total value: ${total_val or 0:.2f}")
db.close()
