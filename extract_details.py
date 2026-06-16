"""Extract ALL detailed information from the email-accountant database."""
import sys, json
sys.path.insert(0, '/opt/data/email-accountant')
from db.database import EmailAccountantDB
from collections import Counter

db = EmailAccountantDB(2026)
c = db._conn

def section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")

# ============================================================
section("1. ALL UNIQUE SENDERS (with names)")
# ============================================================
senders = c.execute("""
    SELECT from_email, from_name, COUNT(*) as cnt 
    FROM emails
    GROUP BY from_email ORDER BY cnt DESC
""").fetchall()
for s in senders:
    name = (s['from_name'] or '')[:40]
    print(f"  {s['cnt']:5d}x | {s['from_email'][:45]:45s} | {name}")
print(f"\n  Total unique senders: {len(senders)}")

# ============================================================
section("2. ALL TO/RECIPIENT ADDRESSES")
# ============================================================
to_rows = c.execute("SELECT DISTINCT to_emails FROM emails WHERE to_emails IS NOT NULL").fetchall()
recipients = set()
for row in to_rows:
    try:
        for e in json.loads(row['to_emails']):
            recipients.add(e.lower())
    except: pass

# Also get raw to_header for plain text addresses
to_hdr = c.execute("SELECT DISTINCT to_header FROM emails WHERE to_header IS NOT NULL AND (to_emails IS NULL OR to_emails = '[]')").fetchall()
import re
for row in to_hdr:
    found = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', row['to_header'])
    for e in found:
        recipients.add(e.lower())

for r in sorted(recipients):
    print(f"  {r}")
print(f"\n  Total unique recipients: {len(recipients)}")

# ============================================================
section("3. ALL CC ADDRESSES")
# ============================================================
cc_rows = c.execute("SELECT DISTINCT cc_emails, cc_header FROM emails WHERE cc_emails IS NOT NULL OR cc_header IS NOT NULL").fetchall()
ccs = set()
for row in cc_rows:
    if row['cc_emails']:
        try:
            for e in json.loads(row['cc_emails']):
                ccs.add(e.lower())
        except: pass
    if row['cc_header']:
        found = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', row['cc_header'])
        for e in found:
            ccs.add(e.lower())
for cc in sorted(ccs):
    print(f"  {cc}")
print(f"\n  Total unique CC: {len(ccs)}")

# ============================================================
section("4. BCC ADDRESSES")
# ============================================================
bcc_rows = c.execute("SELECT DISTINCT bcc_emails FROM emails WHERE bcc_emails IS NOT NULL AND bcc_emails != '[]'").fetchall()
bccs = set()
for row in bcc_rows:
    try:
        for e in json.loads(row['bcc_emails']):
            bccs.add(e.lower())
    except: pass
for bcc in sorted(bccs):
    print(f"  {bcc}")
print(f"\n  Total unique BCC: {len(bccs)}")

# ============================================================
section("5. RETURN PATHS (bounce/verification)")
# ============================================================
paths = c.execute("""
    SELECT return_path, COUNT(*) as cnt FROM emails 
    WHERE return_path IS NOT NULL AND return_path != '' 
    GROUP BY return_path ORDER BY cnt DESC
""").fetchall()
for p in paths:
    print(f"  {p['cnt']:4d}x | {p['return_path'][:70]}")
print(f"\n  Total unique return paths: {len(paths)}")

# ============================================================
section("6. UNSUBSCRIBE URLs/LINKS")
# ============================================================
unsub = c.execute("""
    SELECT list_unsubscribe, COUNT(*) as cnt FROM emails 
    WHERE list_unsubscribe IS NOT NULL AND list_unsubscribe != '' 
    GROUP BY list_unsubscribe ORDER BY cnt DESC
""").fetchall()
for u in unsub[:40]:
    print(f"  {u['cnt']:4d}x | {u['list_unsubscribe'][:100]}")
print(f"\n  Total unique unsubscribe links: {len(unsub)}")
if len(unsub) > 40:
    print(f"  ... and {len(unsub)-40} more")

db.close()
print("\n✅ Done extracting details")
