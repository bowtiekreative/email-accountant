"""Run the full processing pipeline on all pending emails."""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import EmailAccountantDB, init_sqlite
from pipeline.processor import parse_email_financial, classify_merchant, ocr_attachment
from datetime import datetime
import traceback


def strip_html(html: str) -> str:
    """Strip HTML tags and clean up text."""
    if not html:
        return ""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'&#[0-9]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def process_email(db, email_id: int):
    """Full processing pipeline for a single email."""
    email = db.get_email(email_id)
    if not email:
        return None
    
    from_email = email.get('from_email', '') or ''
    subject = email.get('subject', '') or ''
    
    # Get body text (try plain first, fall back to HTML stripping)
    body_text = email.get('body_plain', '') or ''
    if not body_text.strip():
        html = email.get('body_html', '') or ''
        body_text = strip_html(html)
    
    db.log_pipeline_step(email_id, 'extract', 'started')
    
    # Step 1: Parse from email body
    email_record = {
        'subject': subject,
        'body_plain': body_text,
        'snippet': body_text[:200],
        'from_email': from_email,
    }
    financial = parse_email_financial(email_record)
    
    merchant = None
    amount = None
    tx_type = 'unknown'
    confidence = 0.5
    extraction_method = 'email_body'
    txn_date = None
    
    if financial:
        merchant = financial.get('merchant')
        amount = financial.get('amount')
        tx_type = financial.get('transaction_type', 'unknown')
        confidence = 0.7
        extraction_method = financial.get('source', 'email_body')
        txn_date = financial.get('transaction_date')
        db.log_pipeline_step(email_id, 'extract', 'completed',
                            output_data={'merchant': merchant, 'amount': amount, 'method': extraction_method})
    else:
        # No data from body - check if it's actually a financial email anyway
        db.log_pipeline_step(email_id, 'extract', 'skipped',
                            output_data={'reason': 'No financial data found in email body'})
    
    # Step 2: OCR attachments (for receipt PDFs/images)
    if not merchant or not amount:
        attachments = db._conn.execute(
            "SELECT id, filepath FROM attachments WHERE email_id = ? AND ocr_status = 'pending'",
            (email_id,)
        ).fetchall()
        
        for att in attachments:
            att_path = att['filepath']
            if att_path and os.path.exists(att_path):
                ocr_result = ocr_attachment(att_path)
                if ocr_result and ocr_result.get('confidence', 0) > 0.3:
                    db._conn.execute(
                        "UPDATE attachments SET ocr_status='done', ocr_text=?, ocr_confidence=?, ocr_processed_at=datetime('now') WHERE id=?",
                        (ocr_result.get('raw_text', ''), ocr_result.get('confidence', 0), att['id'])
                    )
                    merchant = merchant or ocr_result.get('vendor')
                    amount = amount or ocr_result.get('amount')
                    if not txn_date:
                        txn_date = ocr_result.get('date')
                    confidence = max(confidence, ocr_result.get('confidence', 0))
                    extraction_method = 'ocr'
                else:
                    db._conn.execute(
                        "UPDATE attachments SET ocr_status='error' WHERE id=?",
                        (att['id'],)
                    )
        db._conn.commit()
    
    # Step 3: If still no data from email - check from_email and subject for patterns
    if not merchant and not amount:
        # Try extracting from subject directly
        amt = re.findall(r'\$\s*(\d+\.\d{2})', subject)
        if amt:
            amount = max(float(a) for a in amt)
        
        if amount and '@' in from_email:
            # Use sender domain as merchant hint
            domain = from_email.split('@')[1].split('.')[0]
            merchant = domain.title()
            confidence = 0.4
    
    # Step 4: Classify transaction
    if amount:
        domain, tx_type_class, category, class_conf = classify_merchant(
            merchant or from_email, subject or '', amount
        )
        if tx_type == 'unknown':
            tx_type = tx_type_class
        
        # Update deduction rate
        deduction_rate = 0.0
        if domain == 'business' and tx_type == 'expense':
            if category in ('Travel & Meals', 'Meals & Entertainment'):
                deduction_rate = 0.5
            else:
                deduction_rate = 1.0
        
        tx_data = {
            'email_id': email_id,
            'email_from': from_email,
            'email_subject': subject[:200] if subject else None,
            'email_date': email.get('email_date'),
            'merchant_name': merchant[:100] if merchant else None,
            'merchant_email': from_email,
            'amount': round(amount, 2),
            'transaction_date': txn_date,
            'description': subject[:500] if subject else None,
            'domain': domain,
            'transaction_type': tx_type,
            'category': category,
            'classification_confidence': round(class_conf, 3),
            'classification_method': 'rule',
            'is_deductible': 1 if domain == 'business' and tx_type == 'expense' else 0,
            'deduction_rate': deduction_rate,
            'needs_review': 1 if class_conf < 0.5 else 0,
        }
        tx_id = db.insert_transaction(tx_data)
        
        db.log_pipeline_step(email_id, 'classify', 'completed',
                            model_used='rule',
                            output_data={'domain': domain, 'category': category, 'tx_type': tx_type})
        
        db._conn.execute(
            "UPDATE emails SET email_status='categorized', processed_at=datetime('now') WHERE id=?",
            (email_id,)
        )
        db._conn.commit()
        return tx_id
    
    # No amount found - mark as errored
    db._conn.execute(
        "UPDATE emails SET email_status='errored' WHERE id=?",
        (email_id,)
    )
    db._conn.commit()
    return None


# Initialize
yr = datetime.now().year
init_sqlite(yr)
db = EmailAccountantDB(yr)

# Reset errored to pending for retry
db._conn.execute("UPDATE emails SET email_status='pending' WHERE email_status='errored'")
db._conn.commit()

# Count pending
pending = db._conn.execute("SELECT COUNT(*) as c FROM emails WHERE email_status='pending' OR email_status IS NULL").fetchone()
errored = db._conn.execute("SELECT COUNT(*) as c FROM emails WHERE email_status='errored'").fetchone()
categorized = db._conn.execute("SELECT COUNT(*) as c FROM emails WHERE email_status='categorized'").fetchone()
print(f"📊 Before: {pending['c']} pending, {errored['c']} errored, {categorized['c']} categorized")

# Process in batches
batch_size = 200
total_tx = 0
total_skipped = 0
total_errors = 0

while True:
    emails = db._conn.execute("""
        SELECT id, from_email, subject FROM emails 
        WHERE email_status = 'pending' OR email_status IS NULL
        ORDER BY id DESC LIMIT ?
    """, (batch_size,)).fetchall()
    
    if not emails:
        break
    
    print(f"\n📨 Processing batch of {len(emails)}...")
    for i, row in enumerate(emails):
        if i % 50 == 0 and i > 0:
            print(f"   {i}/{len(emails)}... ({total_tx} txns so far)")
        
        try:
            tx_id = process_email(db, row['id'])
            if tx_id:
                total_tx += 1
            else:
                total_skipped += 1
        except Exception as e:
            total_errors += 1
            db._conn.execute("UPDATE emails SET email_status='errored' WHERE id=?", (row['id'],))
            db._conn.commit()

# Final summary
print(f"\n{'='*60}")
print(f"📊 PIPELINE COMPLETE")
print(f"{'='*60}")

final_pending = db._conn.execute("SELECT COUNT(*) as c FROM emails WHERE email_status='pending' OR email_status IS NULL").fetchone()
final_categorized = db._conn.execute("SELECT COUNT(*) as c FROM emails WHERE email_status='categorized'").fetchone()
final_errored = db._conn.execute("SELECT COUNT(*) as c FROM emails WHERE email_status='errored'").fetchone()
final_txns = db._conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()

print(f"   Total emails:        {final_pending['c'] + final_categorized['c'] + final_errored['c']}")
print(f"   Categorized:         {final_categorized['c']}")
print(f"   Pending:             {final_pending['c']}")
print(f"   No data (errored):   {final_errored['c']}")
print(f"   Transactions:        {final_txns['c']}")

# Show category breakdown
print(f"\n📊 CATEGORY BREAKDOWN:")
cat_stats = db._conn.execute("""
    SELECT domain, transaction_type, category, COUNT(*) as c, ROUND(SUM(amount),2) as total
    FROM transactions GROUP BY domain, transaction_type, category ORDER BY total DESC
""").fetchall()
for s in cat_stats:
    print(f"   {s['domain']:10s} | {s['transaction_type']:8s} | {s['category']:30s} | {s['c']:3d}x | ${s['total']:>8.2f}")

# Needs review
review = db.get_needs_review()
print(f"\n⚠️  Needs review: {len(review)} transactions")

# Show first 10 unclear ones
if review:
    print(f"   First 10:")
    for r in review[:10]:
        print(f"   • {r['merchant_name'] or '?':25s} | ${r['amount']:>7.2f} | {r['domain']:10s}")

# Show recent transactions 
print(f"\n📋 RECENT TRANSACTIONS (last 20):")
txs = db._conn.execute("""
    SELECT merchant_name, amount, domain, category, transaction_type,
           classification_confidence, is_deductible
    FROM transactions ORDER BY id DESC LIMIT 20
""").fetchall()
for t in reversed(txs):
    conf = '⭐' if t['classification_confidence'] >= 0.8 else '🔶' if t['classification_confidence'] >= 0.5 else '⚠️'
    ded = ' Ded' if t['is_deductible'] else ''
    print(f"   {conf} ${t['amount']:>7.2f} | {t['merchant_name'] or '?':25s} | {t['domain']:10s} | {t['category']:25s}{ded}")

db.close()
print(f"\n✅ Done!")
