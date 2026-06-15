"""
Gmail IMAP Scanner — fetch financial emails from ryan@bowtiekreative.com
Stores everything in the email-accountant database with full metadata.
"""

import imaplib
import email
import json
import os
import re
import time
import base64
import hashlib
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GMAIL_USER = "ryan@bowtiekreative.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

if not GMAIL_APP_PASSWORD:
    print("⚠️  GMAIL_APP_PASSWORD not set. Set it via:")
    print(f"   export GMAIL_APP_PASSWORD='your-app-password'")
    print(f"   Or add to ~/.email-accountant/.env")

# Directories
ATTACHMENT_DIR = Path.home() / ".email-accountant" / "attachments"
CRED_DIR = Path.home() / ".email-accountant"

# Financial email search patterns
FINANCIAL_QUERIES = [
    ('receipt_inbox', 'SUBJECT "receipt"'),
    ('invoice', 'SUBJECT "invoice"'),
    ('order_confirmation', 'SUBJECT "order confirmation"'),
    ('paypal_from', 'FROM "paypal.com"'),
    ('stripe_from', 'FROM "stripe.com"'),
    ('payment_received', 'SUBJECT "payment received"'),
    ('payment_failed', 'SUBJECT "payment failed"'), 
    ('payment_declined', 'SUBJECT "declined"'),
    ('subscription', 'SUBJECT "subscription"'),
    ('your_receipt_from', 'SUBJECT "Your receipt"'),
    ('payment_to', 'SUBJECT "payment to"'),
    ('you_sent', 'SUBJECT "you sent"'),
    ('billing', 'SUBJECT "billing"'),
    ('square_from', 'FROM "squareup.com"'),
    ('shopify_from', 'FROM "shopify.com"'),
    ('amazon_order', 'FROM "amazon.com" SUBJECT "order"'),
    ('amazon_shipment', 'FROM "amazon.com" SUBJECT "shipment"'),
    ('uber', 'FROM "uber.com"'),
    ('doordash', 'FROM "doordash.com"'),
    ('netflix', 'FROM "netflix.com"'),
    ('spotify', 'FROM "spotify.com"'),
    ('google_play', 'FROM "googleplay.com"'),
    ('openrouter', 'FROM "openrouter.ai"'),
]


class GmailScanner:
    """Scan Gmail via IMAP and store in the email-accountant database."""
    
    def __init__(self, db=None):
        self.user = GMAIL_USER
        self.password = GMAIL_APP_PASSWORD
        self.mail = None
        self.db = db  # EmailAccountantDB instance
        
        os.makedirs(ATTACHMENT_DIR, exist_ok=True)
        os.makedirs(CRED_DIR, exist_ok=True)
    
    def connect(self):
        """Connect to Gmail IMAP."""
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self.mail.login(self.user, self.password)
        return True
    
    def disconnect(self):
        if self.mail:
            try:
                self.mail.logout()
            except:
                pass
    
    def search_emails(self, folder='"INBOX"', search_query="ALL", max_results=None):
        """Search emails in a folder, return list of (msg_id, raw_email_bytes)."""
        if not self.mail:
            self.connect()
        
        status, _ = self.mail.select(folder)
        if status != "OK":
            print(f"  ⚠️  Could not select folder: {folder}")
            return []
        
        status, messages = self.mail.search(None, search_query)
        if status != "OK":
            return []
        
        msg_ids = messages[0].split()
        if max_results:
            msg_ids = msg_ids[-max_results:]  # Most recent first
        
        results = []
        for mid in reversed(msg_ids):
            status, data = self.mail.fetch(mid, "(RFC822)")
            if status == "OK":
                results.append((mid, data[0][1]))
        
        return results
    
    def search_financial(self, days_back=30, folder='"[Gmail]/All Mail"'):
        """Search for all financial emails using multiple query patterns.
        Gmail stores everything in All Mail — use that for comprehensive scanning."""
        date_since = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        all_results = []
        seen_ids = set()
        
        print(f"\n🔍 Scanning last {days_back} days...")
        
        for label, query in FINANCIAL_QUERIES:
            full_query = f'(SINCE {date_since}) {query}'
            results = self.search_emails(folder, full_query)
            
            for mid, raw in results:
                mid_str = mid.decode() if isinstance(mid, bytes) else str(mid)
                if mid_str not in seen_ids:
                    seen_ids.add(mid_str)
                    all_results.append(raw)
        
        print(f"   Found {len(all_results)} unique financial emails")
        return all_results
    
    def parse_email(self, raw_bytes):
        """Parse raw email bytes into structured dict with full metadata."""
        msg = email.message_from_bytes(raw_bytes)
        
        # Decode headers
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
        
        def parse_address(header_val):
            """Parse email addresses from a header."""
            if not header_val:
                return "", "", ""
            val = decode_val(header_val)
            # Extract name and email
            match = re.search(r'"?([^"]*?)"?\s*<([^>]+)>', val)
            if match:
                return val, match.group(1).strip(), match.group(2).strip().lower()
            # Just an email without name
            match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', val)
            if match:
                return val, "", match.group(0).lower()
            return val, val, ""
        
        def parse_address_list(header_val):
            """Parse multiple email addresses from a header."""
            if not header_val:
                return "", []
            val = decode_val(header_val)
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', val)
            return val, [e.lower() for e in emails]
        
        # Message ID
        message_id = decode_val(msg.get("Message-ID", ""))
        
        # From
        from_full, from_name, from_email = parse_address(msg.get("From", ""))
        
        # To
        to_full, to_emails = parse_address_list(msg.get("To", ""))
        
        # CC
        cc_full, cc_emails = parse_address_list(msg.get("CC", ""))
        
        # BCC
        bcc_full, bcc_emails = parse_address_list(msg.get("BCC", ""))
        
        # Date
        email_date = decode_val(msg.get("Date", ""))
        
        # DKIM / Auth
        dkim = decode_val(msg.get("DKIM-Signature", ""))
        
        # Body
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
        
        # Gmail-specific headers
        gmail_msg_id = decode_val(msg.get("X-GM-MSGID", "")) or message_id
        
        return {
            "message_id": message_id,
            "gmail_message_id": gmail_msg_id,
            "gmail_thread_id": decode_val(msg.get("X-GM-THRID", "")),
            "from_header": from_full,
            "from_email": from_email,
            "from_name": from_name,
            "to_header": to_full,
            "to_emails": json.dumps(to_emails) if to_emails else None,
            "cc_header": cc_full or None,
            "cc_emails": json.dumps(cc_emails) if cc_emails else None,
            "bcc_emails": json.dumps(bcc_emails) if bcc_emails else None,
            "reply_to": decode_val(msg.get("Reply-To", "")),
            "subject": decode_val(msg.get("Subject", "")),
            "snippet": body_plain[:200] if body_plain else "",
            "body_plain": body_plain,
            "body_html": body_html,
            "content_type": msg.get_content_type(),
            "email_date": email_date,
            "received_date": decode_val(msg.get("Received", "")),
            "return_path": decode_val(msg.get("Return-Path", "")),
            "dkim_signature": dkim,
            "spf_status": decode_val(msg.get("Received-SPF", "")),
            "list_unsubscribe": decode_val(msg.get("List-Unsubscribe", "")),
            "in_reply_to": decode_val(msg.get("In-Reply-To", "")),
            "references_header": decode_val(msg.get("References", "")),
            "is_read": not msg.get("X-GMAIL-LABELS", ""),
            "is_spam": 0,
            "email_status": "pending",
            "body_attachments": attachments,
        }
    
    def save_attachments(self, email_id, attachments):
        """Save attachments to disk and return attachment records."""
        att_records = []
        for att in attachments:
            # Generate hash for dedup
            sha256 = hashlib.sha256(att["data"]).hexdigest()
            
            # Save to disk
            att_dir = ATTACHMENT_DIR / str(email_id)
            att_dir.mkdir(parents=True, exist_ok=True)
            filepath = att_dir / att["filename"]
            
            # Avoid overwriting
            counter = 1
            while filepath.exists():
                name, ext = os.path.splitext(att["filename"])
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
    
    def process_email(self, raw_bytes):
        """Parse an email, store in DB, and return results."""
        parsed = self.parse_email(raw_bytes)
        attachments = parsed.pop("body_attachments", [])
        
        if self.db:
            # Insert email
            email_id = self.db.insert_email(parsed)
            
            # Save and store attachments
            att_records = self.save_attachments(email_id, attachments)
            for att_data in att_records:
                self.db.insert_attachment(att_data)
            
            # Log pipeline step
            self.db.log_pipeline_step(email_id, "scan", "completed", 
                                      output_data={"attachments": len(att_records)})
            
            return email_id, parsed, att_records
        
        return None, parsed, []
    
    def scan_and_store(self, days_back=30, folder='"INBOX"', 
                       account_label="personal"):
        """Full scan: fetch financial emails, parse, store in DB."""
        start_time = time.time()
        
        # Ensure account exists
        if self.db:
            # Check if account exists
            conn = self.db._conn
            existing = conn.execute(
                "SELECT id FROM email_accounts WHERE label = ?",
                (account_label,)
            ).fetchone()
            
            if not existing:
                conn.execute(
                    "INSERT INTO email_accounts (label, email_address, provider) VALUES (?, ?, 'gmail')",
                    (account_label, GMAIL_USER)
                )
                conn.commit()
                print(f"  📋 Created account: {account_label} ({GMAIL_USER})")
        
        # Search
        raw_emails = self.search_financial(days_back, folder)
        
        if not raw_emails:
            print("  📭 No financial emails found.")
            return []
        
        # Process each
        results = []
        for i, raw in enumerate(raw_emails):
            print(f"  📨 Processing {i+1}/{len(raw_emails)}...", end=" ", flush=True)
            try:
                email_id, parsed, atts = self.process_email(raw)
                if email_id:
                    results.append({
                        "email_id": email_id,
                        "from": parsed["from_email"],
                        "subject": parsed["subject"][:60],
                        "date": parsed["email_date"],
                        "attachments": len(atts),
                    })
                    print(f"✅ ID={email_id}")
                else:
                    print(f"⚠️  skipped")
            except Exception as e:
                print(f"❌ Error: {e}")
        
        # Log scan
        if self.db:
            elapsed = time.time() - start_time
            self.db.log_scan({
                "scan_type": "incremental",
                "emails_found": len(raw_emails),
                "emails_processed": len(results),
                "new_transactions": 0,
                "duration_seconds": round(elapsed, 2),
                "scan_status": "completed",
            })
        
        print(f"\n✅ Scan complete: {len(results)} emails stored in {time.time()-start_time:.1f}s")
        return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from db.database import EmailAccountantDB, init_sqlite
    
    # Init DB
    year = datetime.now().year
    init_sqlite(year)
    db = EmailAccountantDB(year)
    
    # Run scanner
    scanner = GmailScanner(db)
    try:
        scanner.connect()
        results = scanner.scan_and_store(days_back=90)
        
        print(f"\n📊 Summary:")
        print(f"   Total emails stored: {len(results)}")
        for r in results[:10]:
            print(f"   • {r['from']:35s} | {r['subject'][:50]}")
        
        # Save scan result
        out_path = Path.home() / ".email-accountant" / "latest_scan.json"
        with open(out_path, "w") as f:
            json.dump({"timestamp": datetime.now().isoformat(), "count": len(results), "emails": results}, f, indent=2)
        print(f"\n📄 Scan report saved to {out_path}")
        
    finally:
        scanner.disconnect()
        db.close()
