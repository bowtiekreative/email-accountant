"""
Extract line items from invoice/receipt emails by parsing body text.
Identifies products, services, quantities, unit prices, and totals.

Every extracted line item is stamped with its source email provenance:
email_id, subject, date, and invoice number — so you always know
which email/document each item originated from.
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


def extract_invoice_number(text):
    """Extract invoice/order/receipt number from text."""
    m = re.search(r'(?:[Ii]nvoice|#[Ii]nvoice)\s*#?\s*(\d{4,})', text)
    if m:
        return m.group(1)
    m = re.search(r'(?:Order|Receipt)\s*#?\s*(\d{5,})', text)
    if m:
        return m.group(1)
    return None


def extract_description_before_price(line):
    """Get the description text appearing before a dollar amount."""
    desc = re.sub(r'\$?\d+[\.,]?\d*\s*$', '', line).strip()
    return desc


def looks_like_footer(line):
    """Check if a line looks like a total/subtotal/tax/balance line."""
    l = line.lower().strip()
    return any(x in l for x in [
        'total', 'subtotal', 'tax', 'balance', 'payment',
        'shipping', 'discount', 'coupon', 'credit', 'refund',
        'due', 'paid', 'change due', 'amount due',
    ])


def looks_like_header(line):
    """Check if a line looks like a table header."""
    l = line.lower().strip()
    return any(x in l for x in [
        'qty', 'item', 'description', 'price', 'amount', 'sku',
        'product', 'service', 'unit price', 'order',
    ])


# =====================================================================
# Process all emails with invoice-like subjects
# =====================================================================
print("Extracting invoice line items with full email provenance...")
invoices = c.execute("""
    SELECT e.id, e.from_email, e.subject, e.body_plain, e.snippet, e.email_date
    FROM emails e
    WHERE (LOWER(e.subject) LIKE '%invoice%'
       OR LOWER(e.subject) LIKE '%receipt%'
       OR LOWER(e.subject) LIKE '%order confirmation%'
       OR LOWER(e.subject) LIKE '%purchase%')
    AND e.body_plain IS NOT NULL AND e.body_plain != ''
    ORDER BY e.email_date
""").fetchall()

results = []
total_line_items_found = 0
emails_with_items = 0

for inv in invoices:
    email_id, from_email, subject, body, snippet, email_date = inv
    text = (body or '') + '\n' + (snippet or '')

    # Extract invoice number from this email
    inv_number = extract_invoice_number(subject or '') or extract_invoice_number(text)

    line_items = []
    amounts = re.findall(r'\$?(\d+\.\d{2})', text)
    amounts_float = [float(a) for a in amounts] if amounts else []

    # Try to extract line items from body text
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or len(line) < 5:
            i += 1
            continue
        if looks_like_header(line) or looks_like_footer(line):
            i += 1
            continue

        # Check for quantity pattern: "2 x $19.99" or "2 @ $19.99"
        qty_match = re.search(r'(\d+)\s*[xX@]\s*\$?(\d+\.\d{2})', line)
        if qty_match:
            qty = int(qty_match.group(1))
            unit_price = float(qty_match.group(2))
            desc = line[:qty_match.start()].strip()
            if not desc:
                # Description might be on previous line
                if i > 0:
                    desc = lines[i - 1].strip()
            if desc and not looks_like_footer(desc):
                line_items.append({
                    'description': desc[:120],
                    'quantity': qty,
                    'unit_price': unit_price,
                    'price': round(qty * unit_price, 2),
                    'source': 'body_qty_line',
                })
            i += 1
            continue

        # Check for description + price pattern
        price_match = re.search(r'\$?(\d+\.\d{2})\s*$', line)
        if price_match:
            price = float(price_match.group(1))
            desc = extract_description_before_price(line[:price_match.start()])

            if desc and len(desc) > 3:
                # Skip if it's just numbers/symbols or a footer
                if re.match(r'^[\d\s,.$%()]+$', desc):
                    i += 1
                    continue
                if looks_like_footer(desc):
                    i += 1
                    continue

                line_items.append({
                    'description': desc[:120],
                    'quantity': 1,
                    'unit_price': price,
                    'price': price,
                    'source': 'body_price_line',
                })
        i += 1

    # Also check for HTML table patterns in snippet
    if not line_items and snippet:
        table_matches = re.findall(r'(?:<td[^>]*>)(.*?)(?:</td>)', snippet, re.IGNORECASE)
        if len(table_matches) >= 4:
            # Group by 4 (could be description, qty, price, total)
            for j in range(0, len(table_matches) - 3, 4):
                desc = re.sub(r'<[^>]+>', '', table_matches[j]).strip()
                price_text = re.sub(r'<[^>]+>', '', table_matches[j + 3]).strip()
                price_m = re.search(r'\$?(\d+\.\d{2})', price_text)
                if desc and price_m and len(desc) > 3 and not looks_like_footer(desc):
                    line_items.append({
                        'description': desc[:120],
                        'quantity': 1,
                        'unit_price': float(price_m.group(1)),
                        'price': float(price_m.group(1)),
                        'source': 'html_table',
                    })

    invoice_data = {
        'email_id': email_id,
        'email_subject': str(subject or '')[:200],
        'email_date': str(email_date or ''),
        'email_from': from_email,
        'invoice_number': inv_number,
        'provenance': f"Email#{email_id}: {str(subject or '')[:100]}",
        'amounts': amounts_float,
        'total_from_amounts': max(amounts_float) if amounts_float else None,
        'line_items': line_items,
        'line_item_count': len(line_items),
    }

    if amounts_float or line_items:
        results.append(invoice_data)
        total_line_items_found += len(line_items)
        if line_items:
            emails_with_items += 1

# =====================================================================
# Save full results to JSON — every item stamped with email provenance
# =====================================================================
output = {
    'total_invoice_emails_analyzed': len(invoices),
    'total_emails_with_data': len(results),
    'total_emails_with_line_items': emails_with_items,
    'total_line_items_extracted': total_line_items_found,
    'extracted_at': datetime.now().isoformat(),
    'format_note': 'Every line item includes email_id, email_subject, and provenance so you can trace each item to its source email',
    'invoices': results,
}

with open(os.path.join(OUTPUT_DIR, 'invoice_items.json'), 'w') as f:
    json.dump(output, f, indent=2, default=str)

# =====================================================================
# Also save a flat list of ALL line items (one per row, each with provenance)
# =====================================================================
all_items_flat = []
for inv in results:
    for li in inv['line_items']:
        all_items_flat.append({
            'email_id': inv['email_id'],
            'email_subject': inv['email_subject'],
            'email_date': inv['email_date'],
            'email_from': inv['email_from'],
            'invoice_number': inv['invoice_number'],
            'provenance': inv['provenance'],
            'item_description': li['description'],
            'quantity': li['quantity'],
            'unit_price': li['unit_price'],
            'total_price': li['price'],
            'source': li['source'],
            'parent_invoice_total': inv['total_from_amounts'],
        })

with open(os.path.join(OUTPUT_DIR, 'all_invoice_items_flat.json'), 'w') as f:
    json.dump({
        'generated_at': datetime.now().isoformat(),
        'format': 'Every row is one line item with full email provenance',
        'total_items': len(all_items_flat),
        'items': all_items_flat,
    }, f, indent=2, default=str)

# =====================================================================
# Summary
# =====================================================================
print(f"Analyzed {len(invoices)} invoice/receipt emails")
print(f"  → {len(results)} had extractable data")
print(f"  → {emails_with_items} had specific line items extracted")
print(f"  → {total_line_items_found} individual line items extracted")
print(f"  → Saved to:")
print(f"     {OUTPUT_DIR}/invoice_items.json")
print(f"     {OUTPUT_DIR}/all_invoice_items_flat.json")
print()
print("Every line item is stamped with:")
print("  • email_id       → trace to source email")
print("  • email_subject  → which invoice/receipt")
print("  • email_date     → when it was sent/received")
print("  • invoice_number → vendor's invoice reference")
print("  • provenance     → human-readable 'Email#123: Subject line'")

# Show invoices with most line items
print("\n--- TOP INVOICES BY LINE ITEM COUNT ---")
by_items = sorted(results, key=lambda x: -x['line_item_count'])[:15]
for inv in by_items:
    if inv['line_item_count'] > 0:
        total = inv['total_from_amounts'] or 0
        print(f"  {inv['line_item_count']:3d} items | ${total:>8.2f} | {inv['provenance'][:80]}")

# Bow Tie Kreative specific summary
btk = [i for i in results if 'bowtiekreative' in i['email_from'].lower() or 'bow tie' in i['email_subject'].lower()]
btk_items = sum(i['line_item_count'] for i in btk)
print(f"\nBow Tie Kreative invoices: {len(btk)} emails, {btk_items} line items")
for i in btk[:10]:
    print(f"  Email#{i['email_id']} | {i['line_item_count']:2d} items | ${i['total_from_amounts'] or 0:>7.2f} | {i['email_subject'][:80]}")

db.close()
