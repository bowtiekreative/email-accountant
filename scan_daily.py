#!/usr/bin/env python3
"""
Daily incremental email scan — checks all 7 accounts for new financial emails.
Scans the last 3 days, stores new emails, classifies transactions, reports.
"""
import sys, os, json, time, imaplib, email, hashlib, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/opt/data/email-accountant')
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path

REPO_DIR = Path('/opt/data/email-accountant')
ENV_PATH = REPO_DIR / '.env'
ATTACHMENT_DIR = Path.home() / '.email-accountant' / 'attachments'
YEAR = datetime.now().year
BATCH_SIZE = 50
DAYS_BACK = 3

# Accounts come from the shared config (~/.email-accountant/accounts.json),
# so Gmail + IMAP accounts are managed in one place / the webapp.
from accounts import get_accounts
SCAN_ACCOUNTS = get_accounts(active_only=True)

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

def scan_account(label, email_addr, pwd, imap_host='imap.gmail.com', imap_port=993):
    """Scan one account for new financial emails in last N days."""
    since_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime('%d-%b-%Y')

    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        mail.login(email_addr, pwd)
    except Exception as e:
        return {'error': str(e), 'new_emails': 0}
    
    mail.select('INBOX')
    
    # Collect unique message IDs from all queries
    all_ids = set()
    for query in FINANCIAL_QUERIES:
        try:
            status, msgs = mail.search(None, f'({query}) SINCE {since_date}')
            if status == 'OK':
                ids = set(msgs[0].split())
                all_ids |= ids
        except:
            pass
    
    # Also check All Mail for items not in inbox
    try:
        mail.select('"[Gmail]/All Mail"')
        for query in FINANCIAL_QUERIES:
            try:
                status, msgs = mail.search(None, f'({query}) SINCE {since_date}')
                if status == 'OK':
                    ids = set(msgs[0].split())
                    all_ids |= ids
            except:
                pass
    except:
        pass
    
    total = len(all_ids)
    if total == 0:
        mail.logout()
        return {'new_emails': 0, 'total_emails': 0}
    
    # Fetch all unique messages
    all_raw = []
    sorted_ids = sorted(all_ids, key=lambda x: int(x))
    for batch_start in range(0, total, BATCH_SIZE):
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
        time.sleep(0.2)
    
    mail.logout()
    
    if not all_raw:
        return {'new_emails': 0, 'total_emails': 0}
    
    # Store in database
    from db.database import EmailAccountantDB, init_sqlite
    from pipeline.processor import parse_email_financial, classify_merchant, detect_state
    
    init_sqlite(YEAR)
    db = EmailAccountantDB(YEAR)
    
    row = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()
    if not row:
        db._conn.execute("INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?,?,'gmail',1)", (label, email_addr))
        db._conn.commit()
        row = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()
    account_id = row['id']
    
    stored = 0
    tx_count = 0
    total_amt = 0.0
    
    for raw in all_raw:
        try:
            parsed = parse_email(raw)
            msg_id = parsed.get('message_id', '') or ''
            
            # Dedup
            if msg_id:
                exists = db._conn.execute("SELECT id FROM emails WHERE message_id=? AND account_id=?", (msg_id, account_id)).fetchone()
                if exists:
                    continue
            
            # Store email
            atts = parsed.pop('body_attachments', [])
            parsed['account_id'] = account_id
            eid = db.insert_email(parsed)
            for att in atts[:3]:
                ad = save_attachment(eid, att)
                if ad:
                    ad['email_id'] = eid
                    db.insert_attachment(ad)
            stored += 1
            
            # Classify
            body = (parsed.get('body_plain') or '') or ''
            if not body.strip():
                body = (parsed.get('body_html') or '') or ''
            record = {
                'subject': parsed.get('subject', '') or '',
                'body_plain': body or '',
                'snippet': (parsed.get('snippet') or '')[:200],
                'from_email': parsed.get('from_email', '') or '',
            }
            financial = parse_email_financial(record)
            if financial and financial.get('amount'):
                try:
                    amt = float(financial['amount'])
                    if amt > 0:
                        merchant = str(financial.get('merchant', '') or '')
                        domain, tx_type, category, conf = classify_merchant(
                            merchant or (parsed.get('from_email', '') or ''),
                            str(parsed.get('subject', '') or ''),
                            amt,
                            str(parsed.get('from_email', '') or ''),
                        )
                        db.insert_transaction({
                            'email_id': eid,
                            'account_id': account_id,
                            'email_from': str(parsed.get('from_email', '') or ''),
                            'email_subject': str(parsed.get('subject', '') or '')[:200],
                            'email_date': str(parsed.get('email_date', '') or '')[:25],
                            'merchant_name': merchant[:100],
                            'amount': amt,
                            'currency': financial.get('currency', 'USD'),
                            'description': str(parsed.get('subject', '') or '')[:200],
                            'domain': domain,
                            'transaction_type': tx_type,
                            'category': category,
                            'txn_state': detect_state(str(parsed.get('subject','') or ''), '', category),
                            'classification_method': 'rule',
                            'classification_confidence': conf,
                        })
                        tx_count += 1
                        total_amt += amt
                except: pass
            
            db._conn.execute("UPDATE emails SET email_status='categorized' WHERE id=?", (eid,))
        except:
            pass
    
    db._conn.commit()
    db.close()
    
    return {
        'new_emails': stored,
        'new_transactions': tx_count,
        'total_value': round(total_amt, 2),
    }

# ===== MAIN =====
results = {}
total_new = 0
total_txns = 0
total_val = 0.0

for acct in SCAN_ACCOUNTS:
    label = acct['label']
    email_addr = acct['email']
    pwd = acct.get('password')
    if not pwd:
        print(f"⚠️  {label}: no password")
        continue
    try:
        r = scan_account(label, email_addr, pwd,
                         acct.get('imap_host', 'imap.gmail.com'),
                         acct.get('imap_port', 993))
        results[label] = r
        if 'error' in r:
            print(f"❌ {label}: {r['error']}")
        else:
            ne = r.get('new_emails', 0)
            nt = r.get('new_transactions', 0)
            tv = r.get('total_value', 0)
            print(f"  {label:18s}: {ne} new, {nt} txns, ${tv:.2f}")
            total_new += ne
            total_txns += nt
            total_val += tv
    except Exception as e:
        print(f"❌ {label}: {e}")
    time.sleep(1)  # Rate limit between accounts

print(f"\n{'='*50}")
print(f"  📬 DAILY SCAN SUMMARY")
print(f"{'='*50}")
print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"  Accounts checked: {len([r for r in results.values() if 'error' not in r])}/{len(SCAN_ACCOUNTS)}")
print(f"  New emails:       {total_new}")
print(f"  New transactions: {total_txns}")
if total_txns > 0:
    print(f"  Total value:      ${total_val:,.2f}")
    income = sum(r.get('total_value', 0) for r in results.values())
    print(f"\n  ✅ Scan complete")
else:
    print(f"\n  ✅ No new financial activity found")
