#!/usr/bin/env python3
"""Detailed write-off breakdown."""
from pathlib import Path
import sqlite3

db_path = Path.home() / '.email-accountant' / 'data' / 'email_accountant_2026.db'
conn = sqlite3.connect(str(db_path))

print("=" * 75)
print("  🔍 DETAILED WRITE-OFF BREAKDOWN")
print("=" * 75)

# 1. Professional Services
print("\n✅ PROFESSIONAL SERVICES ($173,472)")
cur = conn.execute("""
    SELECT merchant_name, COUNT(*), ROUND(SUM(ABS(amount)),2)
    FROM transactions WHERE domain='business' AND transaction_type='expense' AND category='Professional Services'
    GROUP BY merchant_name ORDER BY 3 DESC LIMIT 20
""")
for r in cur.fetchall():
    print(f"  ${r[2]:>9,.2f} | {str(r[0])[:45]:45s} | {r[1]}x")

# 2. Software & Subscriptions
print("\n✅ SOFTWARE & SUBSCRIPTIONS ($34,563)")
cur = conn.execute("""
    SELECT merchant_name, COUNT(*), ROUND(SUM(ABS(amount)),2)
    FROM transactions WHERE domain='business' AND transaction_type='expense' AND category='Software & Subscriptions'
    GROUP BY merchant_name ORDER BY 3 DESC LIMIT 20
""")
for r in cur.fetchall():
    print(f"  ${r[2]:>9,.2f} | {str(r[0])[:45]:45s} | {r[1]}x")

# 3. Internet & Telecom
print("\n✅ INTERNET & TELECOM ($18,205)")
cur = conn.execute("""
    SELECT merchant_name, COUNT(*), ROUND(SUM(ABS(amount)),2)
    FROM transactions WHERE domain='business' AND transaction_type='expense' AND category='Internet & Telecom'
    GROUP BY merchant_name ORDER BY 3 DESC LIMIT 15
""")
for r in cur.fetchall():
    print(f"  ${r[2]:>9,.2f} | {str(r[0])[:45]:45s} | {r[1]}x")

# 4. Marketing
print("\n✅ MARKETING & ADVERTISING ($6,228)")
cur = conn.execute("""
    SELECT merchant_name, COUNT(*), ROUND(SUM(ABS(amount)),2)
    FROM transactions WHERE domain='business' AND transaction_type='expense' AND category='Marketing & Advertising'
    GROUP BY merchant_name ORDER BY 3 DESC LIMIT 15
""")
for r in cur.fetchall():
    print(f"  ${r[2]:>9,.2f} | {str(r[0])[:45]:45s} | {r[1]}x")

# 5. Recurring subs
print("\n🔄 LIKELY MONTHLY SUBSCRIPTIONS (3+ charges, $5-$500/mo)")
cur = conn.execute("""
    SELECT merchant_name, ROUND(AVG(ABS(amount)),2), 
           COUNT(*), ROUND(SUM(ABS(amount)),2), category
    FROM transactions 
    WHERE domain='business' AND transaction_type='expense'
    GROUP BY merchant_name
    HAVING COUNT(*) >= 3 AND AVG(ABS(amount)) BETWEEN 5 AND 500
    ORDER BY 4 DESC
    LIMIT 30
""")
for r in cur.fetchall():
    print(f"  ${r[1]:>7,.2f}/mo | {r[2]:>3d}x | ${r[3]:>8,.2f} | {str(r[0])[:40]:40s} | {r[4][:30]}")

# 6. Large one-offs
print("\n💰 LARGE EXPENSES ($1,000+ each)")
cur = conn.execute("""
    SELECT t.merchant_name, t.amount, t.category, t.email_subject, ea.label
    FROM transactions t
    JOIN emails e ON t.email_id = e.id
    JOIN email_accounts ea ON e.account_id = ea.id
    WHERE t.domain='business' AND t.transaction_type='expense' AND ABS(t.amount) >= 1000
    ORDER BY ABS(t.amount) DESC
""")
for r in cur.fetchall():
    print(f"  ${abs(r[1]):>8,.2f} | {str(r[0])[:35]:35s} | {r[2][:30]:30s}")
    print(f"           {(str(r[3] or ''))[:70]}")

conn.close()
