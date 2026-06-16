"""Extract key business relationships, personal contacts, and financial network from the database."""
import sys, json
sys.path.insert(0, '/opt/data/email-accountant')
from db.database import EmailAccountantDB
from collections import Counter

db = EmailAccountantDB(2026)
c = db._conn

def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

# ============================================================
section("KEY BUSINESS RELATIONSHIPS (income sources)")
# ============================================================
income = c.execute("""
    SELECT merchant_name, merchant_email, email_from, COUNT(*) as cnt, ROUND(SUM(amount),2) as total
    FROM transactions WHERE transaction_type = 'income' AND domain = 'business'
    GROUP BY merchant_name ORDER BY total DESC
""").fetchall()
for r in income:
    print(f"  ${r['total']:>8.2f} | {r['cnt']:3d}x | {str(r['merchant_name'] or '')[:40]:40s} | {str(r['email_from'] or '')[:40]}")

# ============================================================
section("KEY CLIENTS / PAYERS")
# ============================================================
payers = c.execute("""
    SELECT merchant_name, merchant_email, email_from, COUNT(*) as cnt, ROUND(SUM(amount),2) as total
    FROM transactions WHERE category = 'Client Payments' 
    GROUP BY merchant_name ORDER BY total DESC
""").fetchall()
for r in payers:
    print(f"  ${r['total']:>8.2f} | {r['cnt']:3d}x | {str(r['merchant_name'] or '')[:40]:40s} | {str(r['email_from'] or '')[:40]}")

# ============================================================
section("SUBCONTRACTORS / PAYEES")
# ============================================================
payees = c.execute("""
    SELECT merchant_name, email_from, COUNT(*) as cnt, ROUND(SUM(amount),2) as total
    FROM transactions WHERE category IN ('Professional Services') AND transaction_type = 'expense'
    GROUP BY merchant_name ORDER BY total DESC
""").fetchall()
for r in payees:
    print(f"  ${r['total']:>8.2f} | {r['cnt']:3d}x | {str(r['merchant_name'] or '')[:40]:40s} | {str(r['email_from'] or '')[:40]}")

# ============================================================
section("ALL PERSONAL CONTACTS (non-business senders)")
# ============================================================
personal_contacts = c.execute("""
    SELECT from_email, from_name, COUNT(*) as cnt 
    FROM emails 
    WHERE from_email LIKE '%gmail.com' OR from_email LIKE '%icloud.com' OR from_email LIKE '%rogers.com' OR from_email LIKE '%shaw.ca' OR from_email LIKE '%telus.net'
    GROUP BY from_email ORDER BY cnt DESC
""").fetchall()
for r in personal_contacts:
    print(f"  {r['cnt']:3d}x | {r['from_email'][:40]:40s} | {str(r['from_name'] or '')[:40]}")

# ============================================================
section("FREELANCE PLATFORMS USED")
# ============================================================
platforms = ['upwork.com', 'fiverr.com', 'toptal.com', 'freelancer.com', 'peopleperhour.com', 'guru.com']
for p in platforms:
    cnt = c.execute("SELECT COUNT(*) FROM emails WHERE from_email LIKE ?", (f'%{p}%',)).fetchone()[0]
    if cnt > 0:
        print(f"  {cnt:4d} emails from {p}")

# ============================================================
section("EMAIL SERVICE PROVIDERS (infrastructure)")
# ============================================================
esp = c.execute("""
    SELECT from_email, COUNT(*) as cnt FROM emails 
    WHERE from_email LIKE '%@mail.' OR from_email LIKE '%@email.' OR from_email LIKE '%@bounce.' OR from_email LIKE '%@emails.'
    GROUP BY from_email ORDER BY cnt DESC LIMIT 20
""").fetchall()
for r in esp:
    print(f"  {r['cnt']:4d}x | {r['from_email'][:60]}")

# ============================================================
section("CANADIAN BUSINESSES / SERVICES")
# ============================================================
canadian = ['whc.ca', 'telus.', 'rogers.com', 'oxio.ca', 'windmobile', 'spud.ca', 'kijiji', 'waveapps.com', 'shopify.com', 'lightspeed', 'freshbooks.com', 'koho.ca', 'bambora.com']
for domain in canadian:
    cnt = c.execute("SELECT COUNT(*) FROM emails WHERE from_email LIKE ?", (f'%{domain}%',)).fetchone()[0]
    if cnt > 0:
        total = c.execute("SELECT ROUND(SUM(amount),2) FROM transactions WHERE email_from LIKE ?", (f'%{domain}%',)).fetchone()[0]
        print(f"  {cnt:4d}x | {domain:30s} | ${total or 0:>8.2f}")

# ============================================================
section("SUBSCRIPTION SERVICES (recurring)")
# ============================================================
subs = ['netflix', 'spotify', 'apple', 'google play', 'openrouter', 'midjourney', 'descript', 'canva', 'adobe', 'github', 'slack', 'zoom', 'discord', 'calendly']
for s in subs:
    cnt = c.execute("SELECT COUNT(*) FROM emails WHERE from_email LIKE ? OR from_email LIKE ?", (f'%{s}%', f'%{s}%')).fetchone()[0]
    if cnt > 0:
        txn_cnt = c.execute("SELECT COUNT(*) FROM transactions WHERE merchant_name LIKE ?", (f'%{s}%',)).fetchone()[0]
        total = c.execute("SELECT ROUND(SUM(amount),2) FROM transactions WHERE merchant_name LIKE ?", (f'%{s}%',)).fetchone()[0]
        print(f"  {cnt:4d} emails | {txn_cnt:3d} txns | ${total or 0:>8.2f} | {s}")

# ============================================================
section("SPENDING BY YEAR (archival)")
# ============================================================
years = c.execute("""
    SELECT strftime('%Y', email_date) as yr, COUNT(*) as emails, 
           COUNT(DISTINCT merchant_name) as merchants,
           ROUND(SUM(amount),2) as total
    FROM transactions 
    GROUP BY yr ORDER BY yr
""").fetchall()
for r in years:
    yr = r['yr'] or '????'
    print(f"  {yr:6s} | {r['emails']:5d} txns | {r['merchants']:4d} merchants | ${r['total'] or 0:>10.2f}")

# ============================================================
section("TOP MERCHANTS BY TOTAL SPEND")
# ============================================================
top = c.execute("""
    SELECT merchant_name, COUNT(*) as cnt, ROUND(SUM(amount),2) as total, domain
    FROM transactions 
    GROUP BY merchant_name ORDER BY total DESC LIMIT 30
""").fetchall()
for r in top:
    print(f"  ${r['total']:>9.2f} | {r['cnt']:4d}x | {str(r['merchant_name'] or '?')[:40]:40s} | {r['domain']}")

db.close()
