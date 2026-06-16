"""
Forensic Reclassification — fix the misclassifications discovered through research.
"""
import sys; sys.path.insert(0, '/opt/data/email-accountant')
from db.database import EmailAccountantDB

db = EmailAccountantDB(2026)
c = db._conn
fixes = 0

def fix(description, sql):
    global fixes
    cur = c.execute(sql)
    c.commit()
    affected = cur.rowcount
    if affected > 0:
        fixes += affected
        print(f"  ✅ {affected} rows: {description}")

# ===================================================================
print("FORENSIC RECLASSIFICATION PASS")
print("=" * 60)

# 1. Waveapps ($45k) — invoicing/payment processing platform
# Money coming IN through Wave Payments = income, not expense
fix("Waveapps: money flowing IN via Wave Payments = income",
    "UPDATE transactions SET domain='business', transaction_type='income', "
    "category='Client Payments', is_deductible=0, deduction_rate=0.0, "
    "classification_confidence=0.90, needs_review=0 "
    "WHERE email_from LIKE '%waveapps%' AND transaction_type='expense'")

# 2. SPUD.ca ($17.8k) — online grocery delivery (personal)
fix("SPUD.ca: online grocery delivery → personal Groceries",
    "UPDATE transactions SET domain='personal', transaction_type='expense', "
    "category='Groceries', is_deductible=0, deduction_rate=0.0, "
    "classification_confidence=0.95, needs_review=0 "
    "WHERE email_from LIKE '%spud.ca%'")

# 3. AppSumo ($8.1k) — software deals marketplace (business)
fix("AppSumo: business software deals → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE (email_from LIKE '%appsumo%' OR merchant_name LIKE '%AppSumo%') "
    "AND domain='personal' AND transaction_type='expense'")

# 4. Podio ($1.3k) — project management software (business)
fix("Podio: project management → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.90, needs_review=0 "
    "WHERE email_from LIKE '%podio%'")

# 5. getimg.ai ($416) — AI image generation platform
fix("getimg.ai: AI image generation → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%getimg%' AND category='Client Payments'")

# 6. WooRank ($426) — SEO analysis tool
fix("WooRank: SEO analysis → business Marketing & Advertising",
    "UPDATE transactions SET category='Marketing & Advertising', "
    "classification_confidence=0.90, needs_review=0 "
    "WHERE email_from LIKE '%woorank%'")

# 7. BCGurus ($392) — Business Catalyst training
fix("BCGurus: Adobe BC training → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%bcgurus%'")

# 8. Book Like a Boss ($5.8k) — appointment scheduling
fix("BookLikeABoss: appointment scheduling → business Software & Subscriptions",
    "UPDATE transactions SET category='Software & Subscriptions', "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%mg.bookme%' AND category='Professional Services'")

# 9. FastSpring ($3k) — payment processor / software reseller
# User bought software through FastSpring (business)
fix("FastSpring: software purchases → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.80, needs_review=0 "
    "WHERE email_from LIKE '%fastspring%'")

# 10. Envato / Envato Elements ($1.4k) — design assets marketplace
fix("Envato: design asset purchases → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE (email_from LIKE '%envato%' OR merchant_name LIKE '%Envato%') "
    "AND domain='personal'")

# 11. Clutch/Just Eat Canada / SkipTheDishes ($458) — food delivery
fix("Just Eat Canada: food delivery → personal Dining Out",
    "UPDATE transactions SET domain='personal', transaction_type='expense', "
    "category='Dining Out', classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%just eat%' AND category='Shopping'")

# 12. AirBnB ($624) — travel accommodation
fix("AirBnB: travel accommodation → personal Travel",
    "UPDATE transactions SET domain='personal', transaction_type='expense', "
    "category='Travel & Meals', classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%airbnb%' AND category='Shopping'")

# 13. FreshBooks ($1k) — accounting software
fix("FreshBooks: accounting → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.90, needs_review=0 "
    "WHERE email_from LIKE '%freshbooks%'")

# 14. Shutterstock ($346) — stock imagery
fix("Shutterstock: stock photos → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%shutterstock%' AND category='Shopping'")

# 15. Restream ($319) — live streaming software
fix("Restream: live streaming → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Marketing & Advertising', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%restream%'")

# 16. Shutterstock/Bigstock — stock photos
fix("Bigstock: stock photos → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%bigstock%'")

# 17. Jobscan ($449) — resume optimization tool
fix("Jobscan: resume tool → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.80, needs_review=0 "
    "WHERE email_from LIKE '%jobscan%' AND domain='personal'")

# 18. Squarespace ($996) — website builder
fix("Squarespace: website builder → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.90, needs_review=0 "
    "WHERE email_from LIKE '%squarespace%' AND domain='personal'")

# 19. Lynda/LinkedIn Learning ($408) — online course platform
fix("Lynda/LinkedIn Learning: professional education → business Professional Services",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Professional Services', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE merchant_name LIKE '%lynda%' AND domain='personal'")

# 20. Zoom ($678) — video conferencing
fix("Zoom: video conferencing → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.90, needs_review=0 "
    "WHERE email_from LIKE '%zoom%' AND category='Shopping'")

# 21. Tome/Magical Tome ($200) — AI presentation tool
fix("Tome: AI presentations → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.80, needs_review=0 "
    "WHERE email_from LIKE '%tome.app%' AND category='Shopping'")

# 22. Paddle ($1,106) — payment processor for SaaS
fix("Paddle: payment processor/SaaS purchases → business Software & Subscriptions",
    "UPDATE transactions SET domain='business', transaction_type='expense', "
    "category='Software & Subscriptions', is_deductible=1, deduction_rate=1.0, "
    "classification_confidence=0.85, needs_review=0 "
    "WHERE email_from LIKE '%paddle%' AND domain='personal'")

c.commit()

# Summary
print(f"\n{'='*60}")
print(f"TOTAL: {fixes} transactions reclassified")
print(f"{'='*60}")

# Show before/after
print("\nDOMAIN/TYPE BREAKDOWN AFTER FIX:")
cats = c.execute("""
    SELECT domain, transaction_type, COUNT(*), ROUND(SUM(amount),2)
    FROM transactions GROUP BY domain, transaction_type ORDER BY SUM(amount) DESC
""").fetchall()
for d, tt, cnt, amt in cats:
    print(f"  {d:10s} | {tt:8s} | {cnt:6d}x | ${amt:>10.2f}")

bad = c.execute("SELECT COUNT(*) FROM transactions WHERE category IN ('Miscellaneous','uncategorized','unresolved')").fetchone()[0]
print(f"\nBad categories: {bad} {'✅' if bad == 0 else '❌'}")

db.close()
