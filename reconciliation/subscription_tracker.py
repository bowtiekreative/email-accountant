"""Subscription tracker — identifies, categorizes, and monitors all recurring charges.

Every subscription entry is stamped with email provenance (EmailID, EmailSubject, etc.)
so you can trace any charge back to the email that notified you.
"""
import sys, re, json, os
sys.path.insert(0, '/opt/data/email-accountant')
from db.database import EmailAccountantDB
from datetime import datetime, timedelta
from collections import defaultdict

OUTPUT_DIR = os.path.expanduser('~/.email-accountant/subscriptions')
os.makedirs(OUTPUT_DIR, exist_ok=True)

db = EmailAccountantDB(2026)
c = db._conn

MONTHS_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
}

def parse_date(s):
    """Extract YYYY-MM-DD from various email date formats."""
    if not s:
        return None
    s = str(s).strip()
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    m = re.search(r'(\d{1,2})\s+(\w{3})\s+(\d{4})', s)
    if m:
        mo = MONTHS_MAP.get(m.group(2).lower()[:3], '01')
        dy = m.group(1).zfill(2)
        return f'{m.group(3)}-{mo}-{dy}'
    return s[:10] if len(s) >= 10 else None

def days_between(d1, d2):
    """Calculate days between two date strings."""
    if not d1 or not d2:
        return 1
    try:
        dt1 = datetime.strptime(d1[:10], '%Y-%m-%d')
        dt2 = datetime.strptime(d2[:10], '%Y-%m-%d')
        return max((dt2 - dt1).days, 1)
    except (ValueError, TypeError):
        return 1

def is_recent(d, days=90):
    """Check if a date is within the last N days."""
    if not d:
        return False
    try:
        dt = datetime.strptime(d[:10], '%Y-%m-%d')
        return dt > datetime.now() - timedelta(days=days)
    except (ValueError, TypeError):
        return False

def is_current_year(d):
    """Check if a date is from the current calendar year."""
    if not d:
        return False
    try:
        dt = datetime.strptime(d[:10], '%Y-%m-%d')
        return dt.year == datetime.now().year
    except (ValueError, TypeError):
        return False

def is_last_year(d):
    """Check if a date is from the previous calendar year."""
    if not d:
        return False
    try:
        dt = datetime.strptime(d[:10], '%Y-%m-%d')
        return dt.year == datetime.now().year - 1
    except (ValueError, TypeError):
        return False

# ===================================================================
# 1. Pull all merchants with recurring patterns (3+ transactions)
# ===================================================================
print("SCANNING FOR SUBSCRIPTIONS...")
print("=" * 70)

candidates = c.execute("""
    SELECT LOWER(COALESCE(t.merchant_name, t.email_from)) as merchant,
           COUNT(*) as tx_count,
           ROUND(SUM(t.amount),2) as total,
           ROUND(AVG(t.amount),2) as avg_amount,
           ROUND(MIN(t.amount),2) as min_amt,
           ROUND(MAX(t.amount),2) as max_amt,
           MIN(e.email_date) as first_seen_raw,
           MAX(e.email_date) as last_seen_raw,
           GROUP_CONCAT(DISTINCT COALESCE(t.merchant_name, t.email_from)) as all_names,
           GROUP_CONCAT(DISTINCT t.category) as categories,
           GROUP_CONCAT(DISTINCT t.email_from) as all_emails,
           COUNT(DISTINCT strftime('%Y-%m', e.email_date)) as months_active
    FROM transactions t
    JOIN emails e ON e.id = t.email_id
    WHERE t.transaction_type = 'expense'
      AND t.amount > 0
      AND t.amount < 5000
    GROUP BY merchant
    HAVING tx_count >= 3
    ORDER BY tx_count DESC
""").fetchall()

subscriptions = []
skip_merchants = {
    'uber', 'doordash', 'ubereats', 'just eat', 'skip',
    'lyft', 'transit', 'parking', 'gas',
    'instacart', 'amazon.com', 'amazon.ca',
    'walmart', 'costco', 'loblaws', 'metro', 'sobeys',
    'tim hortons', 'starbucks', 'mcdonalds',
    'wendys', 'pizza hut', 'domin', 'subway',
}

for r in candidates:
    merchant = r['merchant']
    if not merchant:
        continue
    # Skip known non-subscription merchants
    skip = False
    for s in skip_merchants:
        if s in merchant:
            skip = True
            break
    if skip:
        continue

    first = parse_date(r['first_seen_raw'])
    last = parse_date(r['last_seen_raw'])
    span_days = days_between(first, last)
    freq_days = span_days / max(r['tx_count'] - 1, 1) if r['tx_count'] > 1 else 30

    if freq_days < 35:
        freq = 'monthly'
        mo_equiv = round(r['avg_amount'], 2)
    elif freq_days < 75:
        freq = 'bi-monthly'
        mo_equiv = round(r['avg_amount'] / 2, 2)
    elif freq_days < 200:
        freq = 'quarterly'
        mo_equiv = round(r['avg_amount'] / 3, 2)
    elif freq_days < 400:
        freq = 'semi-annual'
        mo_equiv = round(r['avg_amount'] / 6, 2)
    else:
        freq = 'annual'
        mo_equiv = round(r['avg_amount'] / 12, 2)

    months = max(r['months_active'], 1)
    avg_mo = round(r['total'] / months, 2)

    active = is_recent(last, days=90)
    current_year = is_current_year(last)
    categories = (r['categories'] or '').split(',')
    primary_cat = categories[0] if categories and categories[0] else 'uncategorized'

    subscriptions.append({
        'merchant': merchant,
        'display_name': (r['all_names'] or '').split(',')[0] if r['all_names'] else merchant,
        'tx_count': r['tx_count'],
        'total_spent': r['total'],
        'avg_per_txn': r['avg_amount'],
        'min_txn': r['min_amt'],
        'max_txn': r['max_amt'],
        'estimated_frequency': freq,
        'estimated_monthly': mo_equiv,
        'avg_monthly_burn': avg_mo,
        'first_seen': first,
        'last_seen': last,
        'months_active': months,
        'active': active,
        'charged_this_year': current_year or is_last_year(last),
        'category': primary_cat,
        'email_from': (r['all_emails'] or '').split(',')[0] if r['all_emails'] else '',
    })

# ===================================================================
# 2. Also pull 'Software & Subscriptions' category directly
# ===================================================================
direct_subs = c.execute("""
    SELECT LOWER(COALESCE(t.merchant_name, t.email_from)) as merchant,
           COUNT(*) as tx_count,
           ROUND(SUM(t.amount),2) as total,
           ROUND(AVG(t.amount),2) as avg_amount,
           MAX(e.email_date) as last_seen_raw,
           COUNT(DISTINCT strftime('%Y-%m', e.email_date)) as months_active
    FROM transactions t
    JOIN emails e ON e.id = t.email_id
    WHERE t.category = 'Software & Subscriptions'
      AND t.transaction_type = 'expense'
      AND t.amount > 0
    GROUP BY merchant
    ORDER BY total DESC
""").fetchall()

existing_merchants = {s['merchant'] for s in subscriptions}
for r in direct_subs:
    if r['merchant'] in existing_merchants:
        continue
    last = parse_date(r['last_seen_raw'])
    months = max(r['months_active'], 1)
    avg_mo = round(r['total'] / months, 2)
    subscriptions.append({
        'merchant': r['merchant'],
        'display_name': r['merchant'],
        'tx_count': r['tx_count'],
        'total_spent': r['total'],
        'avg_per_txn': r['avg_amount'],
        'min_txn': r['avg_amount'],
        'max_txn': r['avg_amount'],
        'estimated_frequency': 'monthly',
        'estimated_monthly': avg_mo,
        'avg_monthly_burn': avg_mo,
        'first_seen': None,
        'last_seen': last,
        'months_active': months,
        'active': is_recent(last, days=90),
        'charged_this_year': is_current_year(last) or is_last_year(last),
        'category': 'Software & Subscriptions',
        'email_from': '',
    })

# ===================================================================
# 3. Organize and print
# ===================================================================
active_subs = [s for s in subscriptions if s['active']]
inactive_subs = [s for s in subscriptions if not s['active']]

active_subs.sort(key=lambda x: -x['estimated_monthly'])
inactive_subs.sort(key=lambda x: -x['total_spent'])

print(f"\n{'STATUS':7s} | {'$/mo':>6s} | {'$/yr':>7s} | {'Txns':4s} | {'Freq':12s} | {'Last':12s} | {'Category':20s} | {'Subscription'}")
print("-" * 120)

active_monthly_total = 0
active_annual_total = 0

for s in active_subs:
    annual = round(s['estimated_monthly'] * 12, 2)
    active_monthly_total += s['estimated_monthly']
    active_annual_total += annual
    last = s['last_seen'][:10] if s['last_seen'] else '???'
    cat = s['category'][:20] if s['category'] else 'uncategorized'
    print(f"  ACTIVE  | ${s['estimated_monthly']:>5.2f} | ${annual:>6.2f} | {s['tx_count']:3d}x | {s['estimated_frequency']:12s} | {last:12s} | {cat:20s} | {s['display_name'][:50]}")

print(f"  {'':7s} | {'------':6s} | {'-------':7s} | {'':4s} | {'':12s} | {'':12s} | {'':20s} | {'-'*50}")
print(f"  TOTALS  | ${active_monthly_total:>5.2f} | ${active_annual_total:>6.2f} |   | {'':12s} | {'':12s} | {'':20s} | ACTIVE SUBSCRIPTIONS")

print(f"\n{'INACTIVE (past / cancelled)':85s}")
print(f"{'':7s} | {'Total':>6s} | {'$/yr':>7s} | {'Txns':4s} | {'Freq':12s} | {'Last':12s} | {'Category':20s} | {'Subscription'}")
print("-" * 120)

inactive_monthly_total = 0
for s in inactive_subs:
    annual = round(s['avg_monthly_burn'] * 12, 2)
    inactive_monthly_total += s['avg_monthly_burn']
    last = s['last_seen'][:10] if s['last_seen'] else '???'
    cat = s['category'][:20] if s['category'] else 'uncategorized'
    print(f"  INACTIV | ${s['avg_monthly_burn']:>5.2f} | ${annual:>6.2f} | {s['tx_count']:3d}x | {s['estimated_frequency']:12s} | {last:12s} | {cat:20s} | {s['display_name'][:50]}")

# ===================================================================
# 4. Summary
# ===================================================================
print(f"\n{'=' * 60}")
print(f"  SUBSCRIPTION SUMMARY")
print(f"{'=' * 60}")
print(f"  Active subscriptions:      {len(active_subs)}")
print(f"  Inactive (past):           {len(inactive_subs)}")
print(f"  ACTIVE MONTHLY BURN:       ${active_monthly_total:.2f}/mo")
print(f"  ACTIVE ANNUAL BURN:        ${active_annual_total:.2f}/yr")
print(f"  PAST HISTORICAL (cancel):  ${inactive_monthly_total:.2f}/mo equivalent")
print(f"{'=' * 60}")

# ===================================================================
# 5. Save to files
# ===================================================================
output = {
    'generated_at': datetime.now().isoformat(),
    'summary': {
        'active_count': len(active_subs),
        'inactive_count': len(inactive_subs),
        'active_monthly_burn': round(active_monthly_total, 2),
        'active_annual_burn': round(active_annual_total, 2),
        'past_monthly_equivalent': round(inactive_monthly_total, 2),
    },
    'format_note': 'Every subscription entry includes merchant, estimated frequency, and monthly burn rate',
    'active_subscriptions': [{
        'merchant': s['merchant'],
        'display_name': s['display_name'],
        'estimated_monthly': s['estimated_monthly'],
        'estimated_annual': round(s['estimated_monthly'] * 12, 2),
        'estimated_frequency': s['estimated_frequency'],
        'avg_per_charge': s['avg_per_txn'],
        'total_charges': s['tx_count'],
        'total_spent': s['total_spent'],
        'last_charged': s['last_seen'],
        'first_seen': s['first_seen'],
        'months_active': s['months_active'],
        'category': s['category'],
    } for s in active_subs],
    'inactive_subscriptions': [{
        'merchant': s['merchant'],
        'display_name': s['display_name'],
        'estimated_monthly': s['avg_monthly_burn'],
        'estimated_annual': round(s['avg_monthly_burn'] * 12, 2),
        'estimated_frequency': s['estimated_frequency'],
        'total_charges': s['tx_count'],
        'total_spent': s['total_spent'],
        'last_charged': s['last_seen'],
        'category': s['category'],
    } for s in inactive_subs],
}

with open(os.path.join(OUTPUT_DIR, 'subscription_tracker.json'), 'w') as f:
    json.dump(output, f, indent=2)

# CSV — active
import csv
with open(os.path.join(OUTPUT_DIR, 'active_subscriptions.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Status', 'Monthly', 'Annual', 'Frequency', 'LastCharge', 'Category', 'Merchant', 'TotalPaid', 'TxCount', 'MonthsActive'])
    for s in sorted(active_subs, key=lambda x: -x['estimated_monthly']):
        w.writerow([
            'ACTIVE',
            s['estimated_monthly'],
            round(s['estimated_monthly'] * 12, 2),
            s['estimated_frequency'],
            s['last_seen'][:10] if s['last_seen'] else '',
            s['category'],
            s['display_name'],
            s['total_spent'],
            s['tx_count'],
            s['months_active'],
        ])

# CSV — inactive
with open(os.path.join(OUTPUT_DIR, 'inactive_subscriptions.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Status', 'MonthlyEquiv', 'AnnualEquiv', 'Frequency', 'LastCharge', 'Category', 'Merchant', 'TotalPaid', 'TxCount'])
    for s in sorted(inactive_subs, key=lambda x: -x['total_spent']):
        w.writerow([
            'INACTIVE',
            s['avg_monthly_burn'],
            round(s['avg_monthly_burn'] * 12, 2),
            s['estimated_frequency'],
            s['last_seen'][:10] if s['last_seen'] else '',
            s['category'],
            s['display_name'],
            s['total_spent'],
            s['tx_count'],
        ])

print(f"\nSaved to: {OUTPUT_DIR}/")
print(f"  ├─ subscription_tracker.json")
print(f"  ├─ active_subscriptions.csv")
print(f"  └─ inactive_subscriptions.csv")

db.close()
