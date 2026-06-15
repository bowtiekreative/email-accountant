"""
Email Accountant — Processing Pipeline
Extracts financial data from emails and attachments, classifies transactions.
"""
import os
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Known merchant classification rules
MERCHANT_CATEGORIES = {
    # Business software & services
    'slack': ('business', 'expense', 'Software & Subscriptions'),
    'github': ('business', 'expense', 'Software & Subscriptions'),
    'notion': ('business', 'expense', 'Software & Subscriptions'),
    'figma': ('business', 'expense', 'Software & Subscriptions'),
    'hostinger': ('business', 'expense', 'Internet & Telecom'),
    'digitalocean': ('business', 'expense', 'Internet & Telecom'),
    'aws': ('business', 'expense', 'Internet & Telecom'),
    'google cloud': ('business', 'expense', 'Internet & Telecom'),
    'cloudflare': ('business', 'expense', 'Internet & Telecom'),
    'openrouter': ('business', 'expense', 'Software & Subscriptions'),
    'anthropic': ('business', 'expense', 'Software & Subscriptions'),
    'sendgrid': ('business', 'expense', 'Marketing & Advertising'),
    'hubspot': ('business', 'expense', 'Marketing & Advertising'),
    'mailchimp': ('business', 'expense', 'Marketing & Advertising'),
    'canva': ('business', 'expense', 'Software & Subscriptions'),
    'adobe': ('business', 'expense', 'Software & Subscriptions'),
    'elementor': ('business', 'expense', 'Software & Subscriptions'),
    'facetwp': ('business', 'expense', 'Software & Subscriptions'),
    'robomotion': ('business', 'expense', 'Software & Subscriptions'),
    'mainfunc': ('business', 'expense', 'Software & Subscriptions'),
    # Income processors
    'stripe': None,  # Bi-directional — check direction
    'square': None,  # Bi-directional
    'paypal': None,  # Bi-directional
    'upwork': ('business', 'income', 'Consulting Fees'),
    'fiverr': ('business', 'income', 'Consulting Fees'),
    # Personal
    'netflix': ('personal', 'expense', 'Entertainment'),
    'spotify': ('personal', 'expense', 'Entertainment'),
    'disney+': ('personal', 'expense', 'Entertainment'),
    'uber': None,  # Ambiguous
    'lyft': None,
    'doordash': ('personal', 'expense', 'Dining Out'),
    'ubereats': ('personal', 'expense', 'Dining Out'),
    'walmart': ('personal', 'expense', 'Shopping'),
    'costco': None,
    'amazon': None,
    'google play': ('personal', 'expense', 'Entertainment'),
    'google storage': ('personal', 'expense', 'Software & Subscriptions'),
    'meta platforms': ('business', 'expense', 'Marketing & Advertising'),
    'facebook': ('business', 'expense', 'Marketing & Advertising'),
    'instagram': ('business', 'expense', 'Marketing & Advertising'),
}

# Paid-to names that are business services (PayPal receipts)
BUSINESS_PAYEES = [
    'hostinger', 'github', 'slack', 'digitalocean', 'aws', 'google cloud',
    'cloudflare', 'openrouter', 'anthropic', 'sendgrid', 'hubspot',
    'mailchimp', 'canva', 'adobe', 'elementor', 'facetwp', 'robomotion',
    'mainfunc', 'namecheap', 'godaddy', 'vercel', 'netlify', 'heroku',
    'datadog', 'new relic', 'sentry', 'hotjar', 'intercom', 'zendesk',
    'atlassian', 'jira', 'confluence', 'linear', 'figma', 'notion',
    'monday.com', 'asana', 'trello', 'basecamp',
]

# Personal payees
PERSONAL_PAYEES = [
    'netflix', 'spotify', 'disney', 'hulu', 'hbo', 'paramount',
    'doordash', 'ubereats', 'grubhub', 'postmates',
    'walmart', 'target', 'costco', 'amazon',
    'uber', 'lyft', 'transit',
]

AMOUNT_PATTERNS = [
    r'\$(\d+\.\d{2})',
    r'(?:total|amount)[:\s]*\$?(\d+\.\d{2})',
    r'(?:charged|paid)[:\s]*\$?(\d+\.\d{2})',
]


def extract_amount_from_text(text: str) -> Optional[float]:
    """Extract dollar amount from text."""
    if not text:
        return None
    amounts = re.findall(r'\$(\d+\.\d{2})', text)
    if amounts:
        # Return the largest amount (usually the total)
        return max(float(a) for a in amounts)
    return None


def classify_merchant(name: str, description: str = "", amount: float = 0.0) -> Tuple[str, str, str, float]:
    """
    Classify a transaction using rules.
    Returns (domain, transaction_type, category, confidence).
    """
    name_lower = (name or "").lower().strip()
    desc_lower = (description or "").lower()
    
    # 1. Try direct merchant match
    for key, result in MERCHANT_CATEGORIES.items():
        if key in name_lower:
            if result is not None:
                return (*result, 0.95)
            # None = ambiguous, continue to context clues
    
    # 2. Check payee lists
    if any(p in name_lower for p in BUSINESS_PAYEES):
        return ('business', 'expense', 'Software & Subscriptions', 0.85)
    if any(p in name_lower for p in PERSONAL_PAYEES):
        return ('personal', 'expense', 'Entertainment', 0.80)
    
    # 3. Keyword matching
    business_kw = ['invoice', 'client payment', 'consulting', 'freelance',
                   'contractor', 'office', 'domain', 'hosting', 'subscription',
                   'advertising', 'marketing', 'software', 'cloud', 'server']
    personal_kw = ['grocery', 'gas', 'restaurant', 'entertainment', 'dining']
    
    for kw in business_kw:
        if kw in name_lower or kw in desc_lower:
            return ('business', 'expense', 'uncategorized-business', 0.70)
    for kw in personal_kw:
        if kw in name_lower or kw in desc_lower:
            return ('personal', 'expense', 'uncategorized-personal', 0.70)
    
    # 4. Amount heuristic
    if amount < 30:
        return ('personal', 'expense', 'Miscellaneous', 0.40)
    if amount > 500:
        return ('business', 'expense', 'uncategorized-business', 0.50)
    
    return ('unknown', 'expense', 'uncategorized', 0.0)


# ---------------------------------------------------------------------------
# Email Body Parsers
# ---------------------------------------------------------------------------

def parse_paypal_email(subject: str, body: str) -> Optional[Dict]:
    """Parse PayPal receipt emails to extract transaction data."""
    text = f"{subject} {body}"
    
    # Detect direction: payment sent (expense) or received (income)
    is_sent = bool(re.search(r'(payment to|you sent|you paid|receipt for your payment)', text, re.I))
    is_received = bool(re.search(r'(payment received|you received|money received|received a payment)', text, re.I))
    tx_type = 'expense' if is_sent else ('income' if is_received else 'unknown')
    
    # Extract merchant name
    merchant = None
    
    # Pattern 1: "PAYPAL *MERCHANT" in quotes (most reliable)
    m = re.search(r'\"PAYPAL \*([^\"]+)\"', text)
    if m:
        merchant = m.group(1).strip()
    
    # Pattern 2: "You paid $X.XX to MERCHANT" or "Payment to MERCHANT"
    if not merchant:
        m = re.search(r'[Yy]ou paid\s+\$?\d+\.\d{2}\s+\w+\s+to\s+(.+?)(?:\s*[.\n]|\s*$)', text)
        if m:
            merchant = m.group(1).strip().rstrip('.')
    
    if not merchant:
        m = re.search(r'[Pp]ayment to\s+(.+?)(?:\s*[.\n]|\s*$)', text)
        if m:
            merchant = m.group(1).strip().rstrip('.')
    
    # Pattern 3: "From: MERCHANT" (for received payments)
    if not merchant and is_received:
        m = re.search(r'[Ff]rom:\s*(.+?)(?:\s*[.\n]|\s*$)', text)
        if m:
            merchant = m.group(1).strip()
    
    # Extract amount from "You paid $X.XX"
    amount = None
    m = re.search(r'[Yy]ou\s+(?:paid|sent)\s+\$?(\d+\.\d{2})', text)
    if m:
        amount = float(m.group(1))
    else:
        # "Total $X.XX" (last occurrence)
        amounts = re.findall(r'\$?(\d+\.\d{2})', text)
        if amounts:
            amount = max(float(a) for a in amounts)
    
    # Extract transaction date
    txn_date = None
    m = re.search(r'(?:Transaction date|Date)[:\s]+([A-Z][a-z]+ \d+,? \d{4})', text)
    if m:
        try:
            from datetime import datetime as dt
            txn_date = dt.strptime(m.group(1).replace(',', ''), '%b %d %Y').isoformat()
        except:
            pass
    
    if merchant or amount:
        return {
            'merchant': merchant or 'PayPal',
            'amount': amount,
            'transaction_type': tx_type,
            'source': 'paypal_email',
            'transaction_date': txn_date,
        }
    return None


def parse_stripe_email(subject: str, body: str) -> Optional[Dict]:
    """Parse Stripe receipt emails."""
    text = f"{subject} {body}"
    
    # "Your receipt from MerchantName"
    merchant = None
    m = re.search(r'[Rr]eceipt from (.+?)(?:\s*[-#\n]|\s*$)', text)
    if m:
        merchant = m.group(1).strip()
    
    # "Total charged $XX.XX"
    amount = None
    am = re.search(r'[Tt]otal charged\s*\$?(\d+\.\d{2})', text)
    if am:
        amount = float(am.group(1))
    if not amount:
        am = re.search(r'[Aa]mount\s*\$?(\d+\.\d{2})', text)
        if am:
            amount = float(am.group(1))
    
    if merchant or amount:
        return {
            'merchant': merchant or 'Stripe',
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'stripe_email',
        }
    return None


def parse_uber_email(subject: str, body: str) -> Optional[Dict]:
    """Parse Uber receipt emails."""
    text = f"{subject} {body}"
    
    merchant = "Uber"
    amount = extract_amount_from_text(text)
    
    if amount:
        return {
            'merchant': merchant,
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'uber_email',
        }
    return None


def parse_doordash_email(subject: str, body: str) -> Optional[Dict]:
    """Parse DoorDash receipt emails."""
    text = f"{subject} {body}"
    
    merchant = "DoorDash"
    amount = extract_amount_from_text(text)
    
    if amount:
        return {
            'merchant': merchant,
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'doordash_email',
        }
    return None


def parse_openrouter_email(subject: str, body: str) -> Optional[Dict]:
    """Parse OpenRouter receipt emails."""
    text = f"{subject} {body}"
    
    merchant = "OpenRouter"
    amount = extract_amount_from_text(text)
    
    if amount:
        return {
            'merchant': merchant,
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'openrouter_email',
        }
    return None


# Ordered list of parsers
EMAIL_PARSERS = [
    ('service@intl.paypal.com', parse_paypal_email),
    ('invoice+statements+acct_1KrkPkFnZ21YgCse@stripe.com', parse_stripe_email),
    ('receipts@stripe.com', parse_stripe_email),
    ('receipts+acct_', parse_stripe_email),
    ('invoice+statements@mail.anthropic.com', None),  # Handled by generic
    ('noreply@uber.com', parse_uber_email),
    ('no-reply@doordash.com', parse_doordash_email),
    ('receipts@openrouter.ai', parse_openrouter_email),
]


def parse_email_financial(email_record: dict) -> Optional[Dict]:
    """
    Parse an email record to extract financial transaction data.
    Returns dict with merchant, amount, transaction_type or None.
    """
    subject = email_record.get('subject', '') or ''
    body = email_record.get('body_plain', '') or email_record.get('snippet', '') or ''
    from_email = (email_record.get('from_email', '') or '').lower()
    
    # Try specific parser by sender
    for sender_pattern, parser_func in EMAIL_PARSERS:
        if sender_pattern in from_email and parser_func:
            result = parser_func(subject, body)
            if result:
                return result
    
    # Generic: extract amount and guess merchant
    amount = extract_amount_from_text(f"{subject} {body}")
    
    # Extract payee name from subject
    merchant = None
    # "Receipt for Your Payment to MERCHANT"
    m = re.search(r'[Pp]ayment to (.+)', subject)
    if m:
        merchant = m.group(1).strip()
    elif amount:
        # Use from_email domain as merchant hint
        domain = from_email.split('@')[-1] if '@' in from_email else from_email
        merchant = domain.replace('.com', '').replace('.ai', '').replace('.io', '').title()
    
    if amount or merchant:
        return {
            'merchant': merchant,
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'generic_email',
        }
    
    return None


# ---------------------------------------------------------------------------
# Attachment OCR
# ---------------------------------------------------------------------------

def ocr_attachment(filepath: str) -> Optional[Dict]:
    """
    OCR an attachment and extract receipt data.
    Returns dict with vendor, amount, date, confidence or None.
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        if ext == '.pdf':
            # Try PyMuPDF first
            import fitz
            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text()
            
            # If no text layer (scanned PDF), fallback to OCR
            if len(text.strip()) < 20:
                from pdf2image import convert_from_path
                import pytesseract
                images = convert_from_path(filepath)
                text = ""
                for img in images:
                    from PIL import ImageOps
                    img_gray = img.convert('L')
                    img_gray = ImageOps.autocontrast(img_gray, cutoff=5)
                    text += pytesseract.image_to_string(img_gray, config='--psm 4 --oem 3') + "\n"
            
            doc.close()
            
        elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
            import pytesseract
            from PIL import Image, ImageOps
            img = Image.open(filepath)
            img = img.convert('L')
            img = ImageOps.autocontrast(img, cutoff=5)
            text = pytesseract.image_to_string(img, config='--psm 4 --oem 3')
        else:
            return None
        
        if not text.strip():
            return None
        
        # Extract fields from OCR text
        result = {
            'vendor': None,
            'amount': None,
            'date': None,
            'confidence': 0.0,
            'raw_text': text[:5000],
        }
        
        # Vendor (first non-empty line, or ALL CAPS line)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            # Try ALL CAPS first
            for line in lines[:5]:
                if re.match(r'^[A-Z][A-Z\s&.]+$', line) and len(line) > 3:
                    result['vendor'] = line
                    result['confidence'] += 0.2
                    break
            if not result['vendor']:
                result['vendor'] = lines[0][:50]
                result['confidence'] += 0.1
        
        # Amount
        amt_match = re.search(r'(?:TOTAL|BALANCE DUE|AMOUNT|TOTAL DUE)[:\s]*\$?(\d+\.\d{2})', text, re.I)
        if amt_match:
            result['amount'] = float(amt_match.group(1))
            result['confidence'] += 0.3
        else:
            all_amounts = re.findall(r'\$(\d+\.\d{2})', text)
            if all_amounts:
                result['amount'] = max(float(a) for a in all_amounts)
                result['confidence'] += 0.2
        
        # Date
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
        if date_match:
            try:
                from datetime import datetime as dt
                result['date'] = dt.strptime(date_match.group(1).replace('/', '-'), '%m-%d-%Y').isoformat()
                result['confidence'] += 0.2
            except:
                try:
                    from datetime import datetime as dt
                    result['date'] = dt.strptime(date_match.group(1), '%Y-%m-%d').isoformat()
                    result['confidence'] += 0.2
                except:
                    pass
        
        return result
        
    except Exception as e:
        return {
            'vendor': None,
            'amount': None,
            'date': None,
            'confidence': 0.0,
            'raw_text': f"[Error: {e}]",
        }


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def process_email(db, email_id: int):
    """Process a single email through the full pipeline."""
    email = db.get_email(email_id)
    if not email:
        return None
    
    from_email = email.get('from_email', '') or ''
    subject = email.get('subject', '') or ''
    
    # Step 1: Try parsing from email body
    financial = parse_email_financial(email)
    
    merchant = None
    amount = None
    tx_type = 'unknown'
    confidence = 0.5
    extraction_method = 'email_body'
    
    if financial:
        merchant = financial.get('merchant')
        amount = financial.get('amount')
        tx_type = financial.get('transaction_type', 'unknown')
        confidence = 0.7
        extraction_method = financial.get('source', 'email_body')
        db.log_pipeline_step(email_id, 'extract', 'completed',
                            output_data={'merchant': merchant, 'amount': amount, 'method': extraction_method})
    else:
        db.log_pipeline_step(email_id, 'extract', 'skipped',
                            output_data={'reason': 'No financial data found in email body'})
    
    # Step 2: Try OCR on attachments if no clear data
    if not merchant or not amount:
        attachments = db._conn.execute(
            "SELECT * FROM attachments WHERE email_id = ? AND ocr_status = 'pending'",
            (email_id,)
        ).fetchall()
        
        for att in attachments:
            att_dict = dict(att)
            if att_dict.get('filepath') and os.path.exists(att_dict['filepath']):
                ocr_result = ocr_attachment(att_dict['filepath'])
                if ocr_result and ocr_result.get('confidence', 0) > 0.3:
                    db._conn.execute(
                        "UPDATE attachments SET ocr_status='done', ocr_text=?, ocr_confidence=?, ocr_processed_at=datetime('now') WHERE id=?",
                        (ocr_result.get('raw_text', ''), ocr_result.get('confidence', 0), att_dict['id'])
                    )
                    if not merchant:
                        merchant = ocr_result.get('vendor') or merchant
                    if not amount:
                        amount = ocr_result.get('amount') or amount
                    extraction_method = 'ocr'
                    confidence = max(confidence, ocr_result.get('confidence', 0))
                else:
                    db._conn.execute(
                        "UPDATE attachments SET ocr_status='error' WHERE id=?",
                        (att_dict['id'],)
                    )
        db._conn.commit()
    
    # Step 3: Classify transaction
    if amount and merchant:
        domain, tx_type_class, category, class_conf = classify_merchant(merchant, subject, amount)
        if tx_type == 'unknown':
            tx_type = tx_type_class
    else:
        domain = 'unknown'
        category = 'uncategorized'
        class_conf = 0.0
    
    # Step 4: Store as transaction
    if amount:
        tx_data = {
            'email_id': email_id,
            'email_from': from_email,
            'email_subject': subject,
            'email_date': email.get('email_date'),
            'merchant_name': merchant,
            'merchant_email': from_email,
            'amount': round(amount, 2),
            'description': subject,
            'domain': domain,
            'transaction_type': tx_type,
            'category': category,
            'classification_confidence': round(class_conf, 3),
            'classification_method': 'rule',
            'is_deductible': 1 if domain == 'business' and tx_type == 'expense' else 0,
            'deduction_rate': 0.5 if category == 'Travel & Meals' else (1.0 if domain == 'business' else 0.0),
            'needs_review': 1 if class_conf < 0.5 else 0,
        }
        tx_id = db.insert_transaction(tx_data)
        
        db.log_pipeline_step(email_id, 'classify', 'completed',
                            model_used='rule',
                            output_data={'domain': domain, 'category': category, 'tx_type': tx_type, 'confidence': class_conf})
        
        # Mark email as processed
        db._conn.execute(
            "UPDATE emails SET email_status='categorized', processed_at=datetime('now') WHERE id=?",
            (email_id,)
        )
        db._conn.commit()
        
        return tx_id
    
    db._conn.execute(
        "UPDATE emails SET email_status='errored' WHERE id=?",
        (email_id,)
    )
    db._conn.commit()
    return None


def process_all_unprocessed(db, batch_size: int = 100):
    """Process all emails that haven't been categorized yet."""
    emails = db._conn.execute("""
        SELECT id, from_email, subject FROM emails 
        WHERE email_status = 'pending' OR email_status IS NULL
        ORDER BY id DESC
        LIMIT ?
    """, (batch_size,)).fetchall()
    
    print(f"📨 Processing {len(emails)} unprocessed emails...")
    results = {'transactions': 0, 'skipped': 0, 'errors': 0}
    
    for i, row in enumerate(emails):
        if i % 50 == 0 and i > 0:
            print(f"   Progress: {i}/{len(emails)}...")
        
        try:
            tx_id = process_email(db, row['id'])
            if tx_id:
                results['transactions'] += 1
            else:
                results['skipped'] += 1
        except Exception as e:
            results['errors'] += 1
            db._conn.execute(
                "UPDATE emails SET email_status='errored' WHERE id=?",
                (row['id'],)
            )
            db._conn.commit()
    
    return results


# ---------------------------------------------------------------------------
# CLI / Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from db.database import EmailAccountantDB, init_sqlite
    from datetime import datetime
    
    yr = datetime.now().year
    init_sqlite(yr)
    db = EmailAccountantDB(yr)
    
    # Show pending count
    pending = db._conn.execute("SELECT COUNT(*) as c FROM emails WHERE email_status='pending' OR email_status IS NULL").fetchone()
    categorized = db._conn.execute("SELECT COUNT(*) as c FROM emails WHERE email_status='categorized'").fetchone()
    print(f"📊 Before processing: {pending['c']} pending, {categorized['c']} categorized")
    print()
    
    # Process first 100
    results = process_all_unprocessed(db, batch_size=100)
    
    print(f"\n📊 Results:")
    print(f"   Transactions created: {results['transactions']}")
    print(f"   Skipped (no data): {results['skipped']}")
    print(f"   Errors: {results['errors']}")
    
    # Show what was created
    txs = db.get_transactions(year=yr, limit=20)
    print(f"\n📊 Latest transactions:")
    txs = db._conn.execute("""
        SELECT merchant_name, amount, domain, category, transaction_type, classification_confidence
        FROM transactions ORDER BY id DESC LIMIT 20
    """).fetchall()
    for t in txs:
        conf_star = '⭐' if t['classification_confidence'] >= 0.8 else '🔶' if t['classification_confidence'] >= 0.5 else '⚠️'
        print(f"   {conf_star} {t['merchant_name'] or '?':25s} | ${t['amount']:>7.2f} | {t['domain']:10s} | {t['category']:30s}")
    
    # Summary
    cat_stats = db._conn.execute("""
        SELECT domain, transaction_type, category, COUNT(*) as c, SUM(amount) as total
        FROM transactions GROUP BY domain, transaction_type, category ORDER BY total DESC
    """).fetchall()
    print(f"\n📊 Category breakdown:")
    for s in cat_stats:
        print(f"   {s['domain']:10s} | {s['transaction_type']:8s} | {s['category']:30s} | {s['c']:3d}x | ${s['total']:>8.2f}")
    
    # Needs review
    review = db.get_needs_review()
    print(f"\n⚠️  Needs review: {len(review)} transactions")
    
    db.close()
