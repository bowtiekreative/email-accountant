#!/usr/bin/env python3
"""
Full Archive Scanner — scans ALL financial emails in Gmail (every year, every folder)
Runs as a durable background process that can take hours.
"""
import os, sys, json, time, hashlib, re
from datetime import datetime, timedelta
from pathlib import Path
from email.header import decode_header

# --- Bootstrap: get Gmail password from Proton Pass ---
os.environ['PATH'] = f"{os.path.expanduser('~/.local/bin')}:{os.environ.get('PATH', '')}"
os.environ['PROTON_PASS_KEY_PROVIDER'] = 'fs'
os.environ['PROTON_PASS_SESSION_DIR'] = os.path.join(os.path.expanduser('~'), '.email-accountant', 'pass-session')

# Source PAT from .env
env_path = os.path.join(os.path.expanduser('~'), '.email-accountant', '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k] = v

import subprocess
result = subprocess.run(
    ['pass-cli', 'item', 'view', '--vault-name', 'Messaging',
     '--item-title', 'Gmail ryan@bowtiekreative.com', '--field', 'App Password'],
    capture_output=True, text=True,
    env={**os.environ, 'PROTON_PASS_AGENT_REASON': 'Full Gmail archive scan for email accountant'}
)
gmail_password = result.stdout.strip()

if not gmail_password:
    print("FATAL: Could not retrieve Gmail password from Proton Pass")
    sys.exit(1)

# --- Imports ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import imaplib
import email
from db.database import EmailAccountantDB, init_sqlite
from pipeline.processor import parse_email_financial, classify_merchant, ocr_attachment, strip_html

# --- Config ---
GMAIL_USER = "ryan@bowtiekreative.com"
GMAIL_PASSWORD = gmail_password
ATTACHMENT_DIR = Path.home() / ".email-accountant" / "attachments"
BATCH_SIZE = 100     # Emails per batch
SLEEP_BETWEEN = 2    # Seconds between fetches to avoid rate limits

os.makedirs(ATTACHMENT_DIR, exist_ok=True)

# Financial search queries
FINANCIAL_QUERIES = [
    'SUBJECT "receipt"',
    'SUBJECT "invoice"',
    'SUBJECT "order confirmation"',
    'FROM "paypal.com"',
    'FROM "stripe.com"',
    'SUBJECT "payment received"',
    'SUBJECT "payment failed"',
    'SUBJECT "declined"',
    'SUBJECT "subscription"',
    'SUBJECT "Your receipt"',
    'SUBJECT "payment to"',
    'SUBJECT "you sent"',
    'SUBJECT "billing"',
    'FROM "squareup.com"',
    'FROM "shopify.com"',
    'FROM "amazon.com" SUBJECT "order"',
    'FROM "uber.com"',
    'FROM "doordash.com"',
    'FROM "netflix.com"',
    'FROM "spotify.com"',
    'FROM "googleplay.com"',
    'FROM "openrouter.ai"',
]

# --- Helper: decode email header ---
def decode_val(val):
    if not val:
        return ""
    parts = decode_header(val)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            decoded.append(str(part))
    return " ".join(decoded)

# --- Main Scanner ---
class ArchiveScanner:
    def __init__(self, db):
        self.db = db
        self.mail = None
        self.stats = {
            'total_fetched': 0,
            'total_financial': 0,
            'new_emails': 0,
            'processed': 0,
            'errors': 0,
            'started_at': datetime.now().isoformat(),
        }
    
    def connect(self):
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self.mail.login(GMAIL_USER, GMAIL_PASSWORD)
        return True
    
    def disconnect(self):
        if self.mail:
            try: self.mail.logout()
            except: pass
    
    def scan_all(self):
        """Scan [Gmail]/All Mail with ALL financial queries, NO date filter."""
        if not self.mail:
            self.connect()
        
        query_results = {}  # query -> list of email bytes
        
        for query in FINANCIAL_QUERIES:
            print(f"\n🔍 Query: {query}")
            try:
                status, _ = self.mail.select('"[Gmail]/All Mail"')
                if status != "OK":
                    print(f"  ⚠️  Cannot select All Mail")
                    continue
                
                status, messages = self.mail.search(None, query)
                if status != "OK":
                    print(f"  ⚠️  Search failed")
                    continue
                
                msg_ids = messages[0].split()
                print(f"   Found {len(msg_ids)} matching messages")
                self.stats['total_fetched'] += len(msg_ids)
                
                # Process in batches
                for i in range(0, len(msg_ids), BATCH_SIZE):
                    batch = msg_ids[i:i+BATCH_SIZE]
                    query_results.setdefault(query, []).extend(batch)
                    
                    # Fetch each
                    for mid in batch:
                        try:
                            status, data = self.mail.fetch(mid, "(RFC822)")
                            if status == "OK":
                                self._process_email(mid, data[0][1])
                        except Exception as e:
                            self.stats['errors'] += 1
                        
                    time.sleep(SLEEP_BETWEEN)
                    
                    # Periodic progress
                    if (i // BATCH_SIZE) % 5 == 0 and i > 0:
                        self._report_progress()
                        
            except Exception as e:
                print(f"  ❌ Query error: {e}")
                continue
        
        self.stats['finished_at'] = datetime.now().isoformat()
        return self.stats
    
    def _process_email(self, mid, raw_bytes):
        """Parse and store one email."""
        try:
            # Dedup check by message-id
            msg = email.message_from_bytes(raw_bytes)
            msg_id = decode_val(msg.get("Message-ID", ""))
            
            if msg_id and self.db:
                existing = self.db._conn.execute(
                    "SELECT id FROM emails WHERE message_id = ?", (msg_id,)
                ).fetchone()
                if existing:
                    return  # Already stored
            
            # Parse
            parsed = self._parse_email(raw_bytes)
            attachments = parsed.pop("body_attachments", [])
            
            if self.db:
                email_id = self.db.insert_email(parsed)
                
                # Save attachments
                att_records = self._save_attachments(email_id, attachments)
                for att_data in att_records:
                    self.db.insert_attachment(att_data)
                
                self.db.log_pipeline_step(email_id, "scan", "completed",
                    output_data={"attachments": len(att_records)})
                
                self.stats['new_emails'] += 1
                
                # Quick pipeline: classify immediately
                self._process_transaction(email_id)
                self.stats['processed'] += 1
                
                if self.stats['new_emails'] % 50 == 0:
                    print(f"   ✅ {self.stats['new_emails']} new emails stored and processed")
            
        except Exception as e:
            self.stats['errors'] += 1
    
    def _parse_email(self, raw_bytes):
        """Parse raw email bytes into structured dict."""
        msg = email.message_from_bytes(raw_bytes)
        
        def parse_address(header_val):
            if not header_val:
                return "", "", ""
            val = decode_val(header_val)
            match = re.search(r'"?([^"]*?)"?\s*<([^>]+)>', val)
            if match:
                return val, match.group(1).strip(), match.group(2).strip().lower()
            match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', val)
            if match:
                return val, "", match.group(0).lower()
            return val, val, ""
        
        def parse_address_list(header_val):
            if not header_val:
                return "", []
            val = decode_val(header_val)
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', val)
            return val, [e.lower() for e in emails]
        
        message_id = decode_val(msg.get("Message-ID", ""))
        from_full, from_name, from_email = parse_address(msg.get("From", ""))
        to_full, to_emails = parse_address_list(msg.get("To", ""))
        cc_full, cc_emails = parse_address_list(msg.get("CC", ""))
        email_date = decode_val(msg.get("Date", ""))
        
        body_plain = ""
        body_html = ""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disp = str(part.get("Content-Disposition", ""))
                
                if "attachment" in content_disp or part.get_filename():
                    filename = decode_val(part.get_filename())
                    if filename:
                        att_data = part.get_payload(decode=True)
                        if att_data:
                            attachments.append({
                                "filename": filename,
                                "mime_type": content_type,
                                "size_bytes": len(att_data),
                                "data": att_data,
                            })
                elif content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_plain += payload.decode('utf-8', errors='replace')
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_html += payload.decode('utf-8', errors='replace')
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                content_type = msg.get_content_type()
                if content_type == "text/html":
                    body_html = payload.decode('utf-8', errors='replace')
                else:
                    body_plain = payload.decode('utf-8', errors='replace')
        
        return {
            "message_id": message_id,
            "gmail_message_id": decode_val(msg.get("X-GM-MSGID", "")) or message_id,
            "gmail_thread_id": decode_val(msg.get("X-GM-THRID", "")),
            "from_header": from_full,
            "from_email": from_email,
            "from_name": from_name,
            "to_header": to_full,
            "to_emails": json.dumps(to_emails) if to_emails else None,
            "cc_header": cc_full or None,
            "cc_emails": json.dumps(cc_emails) if cc_emails else None,
            "subject": decode_val(msg.get("Subject", "")),
            "snippet": body_plain[:200] if body_plain else "",
            "body_plain": body_plain,
            "body_html": body_html,
            "content_type": msg.get_content_type(),
            "email_date": email_date,
            "return_path": decode_val(msg.get("Return-Path", "")),
            "dkim_signature": decode_val(msg.get("DKIM-Signature", "")),
            "spf_status": decode_val(msg.get("Received-SPF", "")),
            "list_unsubscribe": decode_val(msg.get("List-Unsubscribe", "")),
            "in_reply_to": decode_val(msg.get("In-Reply-To", "")),
            "references_header": decode_val(msg.get("References", "")),
            "email_status": "pending",
            "body_attachments": attachments,
        }
    
    def _save_attachments(self, email_id, attachments):
        """Save attachments to disk."""
        att_records = []
        for att in attachments:
            sha256 = hashlib.sha256(att["data"]).hexdigest()
            att_dir = ATTACHMENT_DIR / str(email_id)
            att_dir.mkdir(parents=True, exist_ok=True)
            filepath = att_dir / att["filename"]
            
            counter = 1
            name, ext = os.path.splitext(att["filename"])
            while filepath.exists():
                filepath = att_dir / f"{name}_{counter}{ext}"
                counter += 1
            
            with open(filepath, "wb") as f:
                f.write(att["data"])
            
            att_records.append({
                "email_id": email_id,
                "filename": filepath.name,
                "filepath": str(filepath),
                "mime_type": att["mime_type"],
                "size_bytes": att["size_bytes"],
                "hash_sha256": sha256,
                "ocr_status": "pending",
            })
        
        return att_records
    
    def _process_transaction(self, email_id):
        """Quick classify and create a transaction."""
        email = self.db.get_email(email_id)
        if not email:
            return
        
        from_email = email.get('from_email', '') or ''
        subject = email.get('subject', '') or ''
        
        body_text = email.get('body_plain', '') or ''
        if not body_text.strip():
            html = email.get('body_html', '') or ''
            body_text = strip_html(html)
        
        email_record = {
            'subject': subject,
            'body_plain': body_text,
            'snippet': body_text[:200],
            'from_email': from_email,
        }
        
        financial = parse_email_financial(email_record)
        
        merchant = financial.get('merchant') if financial else None
        amount = financial.get('amount') if financial else None
        tx_type = financial.get('transaction_type', 'unknown') if financial else 'unknown'
        
        # Fallback: try extracting from subject
        if not amount:
            amt = re.findall(r'\$\s*(\d+\.\d{2})', subject)
            if amt:
                amount = max(float(a) for a in amt)
        
        if amount:
            domain, tx_type_class, category, class_conf = classify_merchant(
                merchant or from_email, subject or '', amount, from_email
            )
            if tx_type == 'unknown':
                tx_type = tx_type_class
            
            deduction_rate = 1.0 if domain == 'business' and tx_type == 'expense' else 0.0
            
            tx_data = {
                'email_id': email_id,
                'email_from': from_email,
                'email_subject': subject[:200],
                'email_date': email.get('email_date'),
                'merchant_name': (merchant or from_email)[:100],
                'merchant_email': from_email,
                'amount': round(amount, 2),
                'description': subject[:500],
                'domain': domain,
                'transaction_type': tx_type,
                'category': category,
                'classification_confidence': round(class_conf, 3),
                'classification_method': 'rule',
                'is_deductible': 1 if domain == 'business' and tx_type == 'expense' else 0,
                'deduction_rate': deduction_rate,
                'needs_review': 1 if class_conf < 0.5 else 0,
            }
            self.db.insert_transaction(tx_data)
            
            self.db._conn.execute(
                "UPDATE emails SET email_status='categorized', processed_at=datetime('now') WHERE id=?",
                (email_id,)
            )
            self.db._conn.commit()
        else:
            self.db._conn.execute(
                "UPDATE emails SET email_status='skipped' WHERE id=?",
                (email_id,)
            )
            self.db._conn.commit()
    
    def _report_progress(self):
        elapsed = (datetime.now() - datetime.fromisoformat(self.stats['started_at'])).total_seconds()
        rate = self.stats['processed'] / max(elapsed, 1)
        print(f"\n📊 PROGRESS: {self.stats['new_emails']} new emails, "
              f"{self.stats['processed']} processed, "
              f"{self.stats['errors']} errors, "
              f"{rate:.1f}/sec")


# ===== MAIN =====
if __name__ == '__main__':
    yr = datetime.now().year
    
    print("=" * 60)
    print("📧 FULL GMAIL ARCHIVE SCANNER")
    print(f"   Account: {GMAIL_USER}")
    print(f"   Started: {datetime.now().isoformat()}")
    print(f"   Queries: {len(FINANCIAL_QUERIES)}")
    print("=" * 60)
    
    # Init DB
    init_sqlite(yr)
    db = EmailAccountantDB(yr)
    
    # Count existing
    existing = db._conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    print(f"\n📊 Existing emails in DB: {existing}")
    
    # Run scanner
    scanner = ArchiveScanner(db)
    try:
        scanner.connect()
        print("✅ Connected to Gmail\n")
        stats = scanner.scan_all()
        
        print(f"\n{'='*60}")
        print(f"🏁 FULL ARCHIVE SCAN COMPLETE")
        print(f"{'='*60}")
        print(f"   Total queried:     {stats['total_fetched']}")
        print(f"   New emails stored: {stats['new_emails']}")
        print(f"   Processed:         {stats['processed']}")
        print(f"   Errors:            {stats['errors']}")
        
        final_txns = db._conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        final_emails = db._conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        print(f"\n📊 FINAL DATABASE STATE:")
        print(f"   Emails:        {final_emails}")
        print(f"   Transactions:  {final_txns}")
        
        # Category summary
        print(f"\n📊 CATEGORIES:")
        cats = db._conn.execute('''
            SELECT domain, transaction_type, category, COUNT(*), ROUND(SUM(amount),2)
            FROM transactions GROUP BY domain, transaction_type, category ORDER BY SUM(amount) DESC
        ''').fetchall()
        for d, tt, cat, cnt, amt in cats:
            print(f"   {d:10s} | {tt:8s} | {cat:35s} | {cnt:3d}x | ${amt:>8.2f}")
        
        bad = db._conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE category IN ('Miscellaneous','uncategorized','unresolved')"
        ).fetchone()[0]
        print(f"\n❌ Bad categories: {bad} {'✅' if bad == 0 else '❌'}")
        
    finally:
        scanner.disconnect()
        db.close()
    
    print(f"\n✅ Done at {datetime.now().isoformat()}")
