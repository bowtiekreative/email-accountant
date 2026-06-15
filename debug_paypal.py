"""Debug PayPal HTML email structure."""
import sys, re
sys.path.insert(0, '.')

from db.database import EmailAccountantDB
from datetime import datetime

db = EmailAccountantDB(2026)

# Get PayPal HTML body
row = db._conn.execute(
    "SELECT body_html FROM emails WHERE from_email LIKE '%paypal%' LIMIT 1"
).fetchone()
html = row['body_html'] or ''

# Strip HTML tags to get text
text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
text = re.sub(r'<[^>]+>', ' ', text)
text = re.sub(r'&[a-z]+;', ' ', text)
text = re.sub(r'\s+', ' ', text).strip()

print(f"Stripped HTML length: {len(text)} chars")

# Find amounts
amounts = re.findall(r'\$\s*(\d+\.\d{2})', text)
print(f"\nAmounts found: {amounts}")

# Look for merchant after "payment to"
idx = text.lower().find('payment to')
if idx >= 0:
    ctx = text[idx:idx+100]
    print(f"\n'payment to' context: {ctx}")

# Also look for "You sent"
for pat in ['You sent', 'you sent', 'You paid', 'you paid']:
    idx = text.find(pat)
    if idx >= 0:
        print(f"\n'{pat}' at {idx}: {text[idx:idx+100]}")

# Transaction details
for keyword in ['Transaction ID', 'Amount', 'Total', 'Merchant', 'Status']:
    idx = text.lower().find(keyword.lower())
    if idx >= 0:
        print(f"\n'{keyword}' context: {text[idx:idx+80]}")

# Show some structure
print(f"\n--- First 800 chars of stripped text ---")
print(text[:800])
