"""Behavioral spending analysis — identifies patterns and suggests changes."""
import sys, json, os
sys.path.insert(0, '/opt/data/email-accountant')
from db.database import EmailAccountantDB
from datetime import datetime
from collections import defaultdict, Counter

OUTPUT_DIR = os.path.expanduser('~/.email-accountant/insights')
os.makedirs(OUTPUT_DIR, exist_ok=True)

db = EmailAccountantDB(2026)
c = db._conn

print("BEHAVIORAL SPENDING ANALYSIS")
print("=" * 70)

# ===================================================================
# 1. Most frequent merchants (habit indicators)
# ===================================================================
print("\n--- FREQUENCY ANALYSIS (potential habits) ---")
freq = c.execute("""
    SELECT LOWER(COALESCE(merchant_name, email_from)) as name,
           domain, COUNT(*) as cnt, ROUND(SUM(amount),2) as total
    FROM transactions
    WHERE transaction_type = 'expense'
    GROUP BY name ORDER BY cnt DESC LIMIT 30
""").fetchall()
for r in freq:
    print(f"  {r['cnt']:5d}x | ${r['total']:>8.2f} | {r['domain']:10s} | {str(r['name'])[:50]}")

# ===================================================================
# 2. Uber/DoorDash frequency (transportation & food habits)
# ===================================================================
print("\n--- TRANSPORTATION HABITS (Uber) ---")
uber = c.execute("""
    SELECT COUNT(*), ROUND(SUM(amount),2), ROUND(AVG(amount),2),
           MIN(amount), MAX(amount)
    FROM transactions
    WHERE (LOWER(merchant_name) LIKE '%uber%' OR LOWER(email_from) LIKE '%uber.com%')
    AND transaction_type = 'expense'
""").fetchone()
print(f"  Total rides: {uber[0]}")
print(f"  Total spent: ${uber[1]:.2f}")
print(f"  Avg per ride: ${uber[2]:.2f}")
print(f"  Range: ${uber[3]:.2f} - ${uber[4]:.2f}")

# Estimate rides per week
years_uber = c.execute("""
    SELECT COUNT(DISTINCT strftime('%Y', e.email_date)) 
    FROM transactions t JOIN emails e ON e.id = t.email_id
    WHERE (LOWER(t.merchant_name) LIKE '%uber%' OR LOWER(t.email_from) LIKE '%uber.com%')
    AND t.transaction_type = 'expense'
""").fetchone()[0]
avg_weekly = uber[0] / max(years_uber * 52, 1)
print(f"  ~{avg_weekly:.1f} rides/week average")

# ===================================================================
# 3. Food delivery habits
# ===================================================================
print("\n--- FOOD DELIVERY HABITS ---")
food = c.execute("""
    SELECT LOWER(COALESCE(merchant_name, email_from)) as name,
           COUNT(*) as cnt, ROUND(SUM(amount),2) as total
    FROM transactions
    WHERE (LOWER(merchant_name) LIKE '%doordash%' OR LOWER(email_from) LIKE '%doordash%'
           OR LOWER(merchant_name) LIKE '%ubereats%' OR LOWER(merchant_name) LIKE '%just eat%'
           OR LOWER(merchant_name) LIKE '%skip%')
    AND transaction_type = 'expense'
    GROUP BY name ORDER BY total DESC
""").fetchall()
for r in food:
    print(f"  {r['cnt']:4d}x | ${r['total']:>8.2f} | {str(r['name'])[:50]}")
food_total = sum(r['total'] for r in food)
food_count = sum(r['cnt'] for r in food)
print(f"  TOTAL: {food_count} deliveries, ${food_total:.2f}")
print(f"  ~${food_total/max(years_uber * 12, 1):.2f}/month on food delivery")

# ===================================================================
# 4. Subscription bloat
# ===================================================================
print("\n--- SUBSCRIPTION BLOAT ANALYSIS ---")
subs = c.execute("""
    SELECT LOWER(COALESCE(merchant_name, email_from)) as merchant,
           COUNT(*) as cnt, ROUND(SUM(amount),2) as total
    FROM transactions
    WHERE category = 'Software & Subscriptions' AND transaction_type = 'expense'
    GROUP BY merchant ORDER BY total DESC
""").fetchall()

active_subs = []
for s in subs:
    # Check if there were charges in last 2 years
    recent = c.execute("""
        SELECT COUNT(*) FROM transactions t
        JOIN emails e ON e.id = t.email_id
        WHERE LOWER(COALESCE(t.merchant_name, t.email_from)) = ?
        AND t.category = 'Software & Subscriptions'
        AND e.email_date >= date('now', '-2 years')
    """, (s['merchant'],)).fetchone()[0]
    
    status = '🟢 Active' if recent > 0 else '🔴 Inactive'
    monthly = round(s['total'] / max(s['cnt'], 1), 2)
    print(f"  {status:12s} | ${s['total']:>7.2f} total | ~${monthly:>5.2f}/txn | {str(s['merchant'])[:50]}")

total_subs = sum(r['total'] for r in subs)
print(f"\n  TOTAL SUBSCRIPTION SPEND: ${total_subs:.2f}")

# ===================================================================
# 5. Entertainment & impulse spending
# ===================================================================
print("\n--- ENTERTAINMENT & IMPULSE SPENDING ---")
entertainment = c.execute("""
    SELECT LOWER(COALESCE(merchant_name, email_from)) as merchant,
           COUNT(*) as cnt, ROUND(SUM(amount),2) as total
    FROM transactions
    WHERE category = 'Entertainment' AND transaction_type = 'expense' AND domain = 'personal'
    GROUP BY merchant ORDER BY total DESC LIMIT 20
""").fetchall()
for r in entertainment:
    print(f"  ${r['total']:>7.2f} | {r['cnt']:4d}x | {str(r['merchant'])[:50]}")

# ===================================================================
# 6. Savings opportunities
# ===================================================================
print("\n--- SAVINGS OPPORTUNITIES ---")
print("""
  Based on spending patterns, here are the biggest savings levers:

  1. UBER: ${:.2f} total — {} rides. 
     If you got a car: ~$500/mo insurance + $300/mo gas + $400/mo payment = $1,200/mo
     Current Uber spend: ~${:.0f}/mo
     → {} would need to drop to be cheaper than car ownership

  2. FOOD DELIVERY: ${:.2f} total — ${:.0f}/mo
     Cooking at home saves ~60% → potential savings of ${:.0f}/mo

  3. SUBSCRIPTIONS: ${:.2f} across {} services
     Auditing unused subs could save 15-25%

  4. GOOGLE PLAY: Major entertainment spending
     In-app purchases add up — review what apps you're actually using
""".format(
    uber[1], uber[0], uber[1]/max(years_uber * 12, 1),
    uber[1]/max(years_uber * 12, 1) / 1200,
    food_total, food_total/max(years_uber * 12, 1),
    food_total/max(years_uber * 12, 1) * 0.6,
    total_subs, len(subs)
))

# ===================================================================
# 7. Save to file
# ===================================================================
print("\n--- SAVING REPORT ---")
report = {
    'generated_at': datetime.now().isoformat(),
    'uber': {
        'total_rides': uber[0],
        'total_spent': round(uber[1], 2),
        'avg_per_ride': round(uber[2], 2),
        'range': [round(uber[3], 2), round(uber[4], 2)],
    },
    'food_delivery': {
        'total_orders': food_count,
        'total_spent': round(food_total, 2),
    },
    'subscriptions': {
        'total_active': len([s for s in subs if c.execute(
            "SELECT COUNT(*) FROM transactions t JOIN emails e ON e.id=t.email_id "
            "WHERE LOWER(COALESCE(t.merchant_name,t.email_from))=?"
            " AND t.category='Software & Subscriptions'"
            " AND e.email_date >= date('now','-2 years')",
            (s['merchant'],)).fetchone()[0] > 0]),
        'total_spent': round(total_subs, 2),
    },
    'top_habits': [(str(r['name'])[:50], r['cnt'], round(r['total'],2)) for r in freq[:10]],
}

with open(os.path.join(OUTPUT_DIR, 'behavioral_insights.json'), 'w') as f:
    json.dump(report, f, indent=2)
print(f"  → Saved to {OUTPUT_DIR}/behavioral_insights.json")
print(f"  → All insight files in: {OUTPUT_DIR}/")

db.close()
