#!/usr/bin/env python3
"""
Fast Full Archive Scanner — batch-fetches financial emails from ALL accounts.
Uses IMAP batch FETCH (comma-separated IDs) instead of one-at-a-time fetches.
Scans every message in every account's entire Gmail history.
"""
import sys, os, json, time, imaplib, email, hashlib, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from email.header import decode_header
from pathlib import Path
from db.database import EmailAccountantDB, init_sqlite

REPO_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = REPO_DIR / ".env"
ATTACHMENT_DIR = Path.home() / ".email-accountant" / "attachments"
YEAR = datetime.now().year
BATCH_SIZE = 100
SLEEP_BETWEEN_QUERIES = 0.5

# ── ALL accounts ──
ACCOUNTS = [
    ('theapprentice4', 'theapprentice4@gmail.com', 'GMAIL_APPRENTICE_PASSWORD'),
    ('digitalstemcell', 'digitalstemcell@gmail.com', 'GMAIL_DIGITALSTEMCELL_PASSWORD'),
    ('bowtiekreative', 'bowtiekreative@gmail.com', 'GMAIL_BOWTIEKREATIVE_PASSWORD'),
    ('k6rb1n', 'k6rb1n@gmail.com', 'GMAIL_K6RB1N_PASSWORD'),
    ('bnelsonblog1', 'bnelsonblog1@gmail.com', 'GMAIL_BNELSONBLOG1_PASSWORD'),
    ('hustlezonetv', 'hustlezonetv@gmail.com', 'GMAIL_HUSTLEZONETV_PASSWORD'),
]

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
    else:
        sha = ''
    return {'filename': safe, 'filepath': str(fp), 'mime_type': part.get_content_type(),
            'size_bytes': len(payload) if payload else 0, 'hash_sha256': sha}

def scan_account(label, email_addr, env_key):
    """Scan one account's full archive with batch IMAP fetching."""
    pwd = get_pwd(env_key)
    if not pwd:
        return {'error': 'no password in .env'}

    print(f"\n{'='*60}", flush=True)
    print(f"📧 FULL ARCHIVE: {email_addr} ({label})", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Started: {datetime.now().isoformat()}", flush=True)

    # ── Connect ──
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(email_addr, pwd)
    mail.select('"[Gmail]/All Mail"')
    print(f"  ✅ Connected", flush=True)

    # ── Phase 1: Collect ALL unique message IDs from ALL queries ──
    all_ids = set()
    for i, query in enumerate(FINANCIAL_QUERIES):
        try:
            status, msgs = mail.search(None, f'({query})')
            if status != 'OK': continue
            ids = set(msgs[0].split())
            n_old = len(all_ids)
            all_ids |= ids
            n_new = len(all_ids) - n_old
            print(f"  📨 Q{i:2d}: {len(ids):>5d} results (+{n_new} new)", flush=True)
            time.sleep(SLEEP_BETWEEN_QUERIES)
        except Exception as e:
            print(f"  ⚠️  Q{i} error: {e}", flush=True)

    total_unique = len(all_ids)
    print(f"\n  📊 Total unique financial messages: {total_unique}", flush=True)
    if total_unique == 0:
        mail.logout()
        return {'total_emails': 0, 'new_emails': 0}

    # ── Phase 2: Batch-fetch all unique messages ──
    print(f"  📥 Batch-fetching (BATCH_SIZE={BATCH_SIZE})...", flush=True)
    all_raw = []
    sorted_ids = sorted(all_ids, key=lambda x: int(x))

    for batch_start in range(0, total_unique, BATCH_SIZE):
        batch = sorted_ids[batch_start:batch_start + BATCH_SIZE]
        id_str = ','.join(x.decode() if isinstance(x, bytes) else str(x) for x in batch)
        try:
            status, data = mail.fetch(id_str, '(RFC822)')
            if status == 'OK':
                for i in range(0, len(data), 2):
                    if data[i] and isinstance(data[i], tuple):
                        all_raw.append(data[i][1])
        except Exception:
            for mid in batch:
                try:
                    st, d = mail.fetch(mid, '(RFC822)')
                    if st == 'OK' and d[0]:
                        all_raw.append(d[0][1])
                except:
                    pass
        if (batch_start // BATCH_SIZE) % 5 == 0 and batch_start > 0:
            print(f"     ... fetched {batch_start}/{total_unique}", flush=True)

    mail.logout()
    fetched = len(all_raw)
    print(f"  ✅ Fetched {fetched} unique messages", flush=True)
    if fetched == 0:
        return {'total_emails': 0, 'new_emails': 0}

    # ── Phase 3: Store & process ──
    init_sqlite(YEAR)
    db = EmailAccountantDB(YEAR)

    # Resolve account_id
    row = db._conn.execute("SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)).fetchone()
    account_id = row['id'] if row else None
    if not account_id:
        db._conn.execute(
            "INSERT INTO email_accounts (label, email_address, provider, is_active) VALUES (?,?,'gmail',1)",
            (label, email_addr)
        )
        db._conn.commit()
        account_id = db._conn.execute(
            "SELECT id FROM email_accounts WHERE email_address=?", (email_addr,)
        ).fetchone()['id']

    existing_before = db._conn.execute(
        "SELECT COUNT(*) FROM emails WHERE account_id=?", (account_id,)
    ).fetchone()[0]
    print(f"     Account ID={account_id}, existing={existing_before}", flush=True)

    stored = 0
    tx_count = 0
    skipped = 0

    from pipeline.processor import parse_email_financial, classify_merchant

    for i, raw in enumerate(all_raw):
        if i % 200 == 0 and i > 0:
            db._conn.commit()
            print(f"     ... {i}/{fetched} ({stored} new, {tx_count} txns, {skipped} dupes)", flush=True)

        try:
            parsed = parse_email(raw)
            msg_id = parsed.get('message_id', '') or ''

            # Dedup
            if msg_id:
                r2 = db._conn.execute(
                    "SELECT id FROM emails WHERE message_id=? AND account_id=?",
                    (msg_id, account_id)
                ).fetchone()
                if r2:
                    skipped += 1
                    continue

            # Insert email
            atts = parsed.pop('body_attachments', [])
            parsed['account_id'] = account_id
            eid = db.insert_email(parsed)

            # Save attachments (first 5 per email to avoid bloat)
            for att in atts[:5]:
                ad = save_attachment(eid, att)
                if ad:
                    ad['email_id'] = eid
                    db.insert_attachment(ad)

            stored += 1

            # Classify & create transaction
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
                            'description': str(parsed.get('subject', '') or '')[:200],
                            'domain': domain,
                            'transaction_type': tx_type,
                            'category': category,
                            'classification_method': 'rule',
                            'classification_confidence': conf,
                        })
                        tx_count += 1
                except (ValueError, TypeError):
                    pass

            db._conn.execute(
                "UPDATE emails SET email_status='categorized' WHERE id=?", (eid,)
            )

        except Exception:
            pass

    db._conn.commit()

    total_after = db._conn.execute(
        "SELECT COUNT(*) FROM emails WHERE account_id=?", (account_id,)
    ).fetchone()[0]
    total_tx = db._conn.execute(
        "SELECT COUNT(*) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?",
        (account_id,)
    ).fetchone()[0]
    total_val = db._conn.execute(
        "SELECT ROUND(SUM(ABS(amount)),2) FROM transactions t JOIN emails e ON e.id=t.email_id WHERE e.account_id=?",
        (account_id,)
    ).fetchone()[0]

    db.close()

    print(f"\n  ✅ {label} — FULL ARCHIVE COMPLETE:", flush=True)
    print(f"     New emails stored: {stored}", flush=True)
    print(f"     Total emails:      {total_after}", flush=True)
    print(f"     Total transactions: {total_tx}", flush=True)
    print(f"     Total value:       ${total_val or 0:.2f}", flush=True)

    return {
        'email': email_addr,
        'new_emails': stored,
        'total_emails': total_after,
        'new_transactions': tx_count,
        'total_transactions': total_tx,
        'total_value': round(total_val or 0, 2),
    }


# ── Main ──
results_summary = {}

for label, email_addr, env_key in ACCOUNTS:
    try:
        results_summary[label] = scan_account(label, email_addr, env_key)
    except Exception as e:
        print(f"\n  ❌ {label} FAILED: {e}", flush=True)
        import traceback
        traceback.print_exc()
        results_summary[label] = {'error': str(e)}

# Final report
print(f"\n\n{'='*60}", flush=True)
print(f"✅ FULL ARCHIVE COMPLETE — ALL ACCOUNTS", flush=True)
print(f"{'='*60}", flush=True)
print(f"{'Account':20s} | {'New Emails':>10s} | {'Total Emails':>12s} | {'New Txns':>8s} | {'Total Txns':>10s} | {'Total Value':>12s}", flush=True)
print("-" * 80, flush=True)

t_emails = 0; t_txns = 0; t_value = 0.0
for label, info in results_summary.items():
    ne = info.get('new_emails', 0)
    te = info.get('total_emails', 0)
    nt = info.get('new_transactions', 0)
    tt = info.get('total_transactions', 0)
    tv = info.get('total_value', 0)
    err = info.get('error', '')
    suffix = f" ❌ {err}" if err else ""
    print(f"  {label:18s} | {ne:>8d}   | {te:>10d}    | {nt:>6d}   | {tt:>8d}    | ${tv:>8.2f}{suffix}", flush=True)
    t_emails += te; t_txns += tt; t_value += tv

print("-" * 80, flush=True)
print(f"  {'TOTAL':18s} | {'':>8s}   | {t_emails:>10d}    | {'':>6s}   | {t_txns:>8d}    | ${t_value:>8.2f}", flush=True)

report_path = Path.home() / ".email-accountant" / "scans" / f"full_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
os.makedirs(report_path.parent, exist_ok=True)
with open(report_path, 'w') as f:
    json.dump({'completed_at': datetime.now().isoformat(), 'accounts': results_summary}, f, indent=2)
print(f"\n📄 Report saved: {report_path}", flush=True)
print(f"✅ Done at {datetime.now().isoformat()}", flush=True)
