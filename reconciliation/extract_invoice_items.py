"""
Extract line items from invoice/receipt emails by parsing body text.
Identifies products, services, quantities, unit prices, and totals.
"""
import sys, re, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import EmailAccountantDB
from datetime import datetime
from collections import defaultdict

DB_PATH = os.path.expanduser('~/.email-accountant/data/email_accountant_2026.db')
OUTPUT_DIR = os.path.expanduser('~/.email-accountant/invoice_items')
os.makedirs(OUTPUT_DIR, exist_ok=True)

db = EmailAccountantDB(2026)
c = db._conn

# Invoice patterns
INVOICE_PATTERNS = {
    'bowtie_kreative_sent': {
        'pattern': r'Invoice #(\d+)',
        'type': 'outgoing',
        'client_extract': r'Invoice #\d+ from Bow Tie Kreative'
    },
    'bowtie_kreative_received': {
        'pattern': r'(?:Invoice|Receipt) #(\d+)',
        'type': 'incoming',
    },
    'amount_pattern': r'\$?(\d+\.\d{2})',
    'line_item': r'(?:^|\n)\s*(.+?)\s{2,}\$?(\d+\.\d{2})',
    'quantity': r'(\d+)\s*x\s*\$?(\d+\.\d{2})',
}

# Process all emails with invoice subjects
print("Extracting invoice line items...")
invoices = c.execute("""
    SELECT e.id, e.from_email, e.subject, e.body_plain, e.snippet, e.email_date
    FROM emails e
    WHERE (LOWER(e.subject) LIKE '%invoice%' 
       OR LOWER(e.subject) LIKE '%receipt%'
       OR LOWER(e.subject) LIKE '%order confirmation%')
    AND e.body_plain IS NOT NULL AND e.body_plain != ''
    ORDER BY e.email_date
""").fetchall()

results = []
for inv in invoices:
    email_id, from_email, subject, body, snippet, email_date = inv
    text = (body or '') + '\n' + (snippet or '')
    
    invoice_data = {
        'email_id': email_id,
        'from': from_email,
        'subject': str(subject or '')[:200],
        'date': str(email_date or ''),
        'amounts': [],
        'line_items': [],
        'invoice_number': None,
    }
    
    # Extract all dollar amounts
    amounts = re.findall(r'\$?(\d+\.\d{2})', text)
    if amounts:
        invoice_data['amounts'] = [float(a) for a in amounts]
    
    # Try to find invoice number
    inv_match = re.search(r'[Ii]nvoice\s*#?\s*(\d+)', text)
    if inv_match:
        invoice_data['invoice_number'] = inv_match.group(1)
    
    # Try to extract line items (description + price on same/adjacent lines)
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Check for price pattern
        price_match = re.search(r'\$?(\d+\.\d{2})', line)
        if price_match:
            price = float(price_match.group(1))
            # Get description (text before the price)
            desc = re.sub(r'\$?\d+\.\d{2}.*$', '', line).strip()
            if desc and len(desc) > 3 and not re.match(r'^[\d\s,.$%()]+$', desc):
                # Filter out headers/footers
                if not any(x in desc.lower() for x in ['total', 'subtotal', 'tax', 'balance', 'payment']):
                    invoice_data['line_items'].append({
                        'description': desc[:100],
                        'price': price,
                        'source': 'body_text'
                    })
        i += 1
    
    if amounts or invoice_data['line_items']:
        results.append(invoice_data)

# Save results
output = {
    'total_invoices_analyzed': len(invoices),
    'total_with_data': len(results),
    'invoices': results,
    'extracted_at': datetime.now().isoformat(),
}

with open(os.path.join(OUTPUT_DIR, 'invoice_items.json'), 'w') as f:
    json.dump(output, f, indent=2, default=str)

print(f"Analyzed {len(invoices)} invoice emails")
print(f"  → {len(results)} had extractable data")
print(f"  → Saved to {OUTPUT_DIR}/invoice_items.json")

# Summary statistics
total_amount = sum(max(i['amounts']) if i['amounts'] else 0 for i in results)
print(f"\nTotal invoice value detected: ${total_amount:.2f}")

# Show Bow Tie Kreative invoices
btk = [i for i in results if 'bowtiekreative' in i['from'].lower() or 'bow tie' in i['subject'].lower()]
print(f"\nBow Tie Kreative invoice emails: {len(btk)}")
for i in btk[:10]:
    print(f"  #{i['email_id']} | ${max(i['amounts']):>7.2f} | {i['subject'][:80]}")

db.close()
