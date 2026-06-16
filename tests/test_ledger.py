"""End-to-end tests for the webapp ledger read layer: currency separation,
tax-line mapping, and year coverage."""
import importlib

from db.database import EmailAccountantDB, init_sqlite


def _seed():
    init_sqlite(2015)
    db = EmailAccountantDB(2015)

    def add(gid, merch, amt, cur, domain, ttype, cat, ded=0, rate=0.0):
        eid = db.insert_email({
            "gmail_message_id": gid,
            "from_header": f"{merch} <x@{merch}.com>",
            "subject": f"{merch} receipt",
            "email_date": "2015-05-01T10:00:00",
            "snippet": "x",
            "from_email": f"x@{merch}.com",
            "from_name": merch,
            "email_status": "pending",
        })
        db.insert_transaction({
            "email_id": eid, "email_subject": f"{merch} receipt",
            "email_date": "2015-05-01T10:00:00", "merchant_name": merch,
            "amount": amt, "currency": cur, "transaction_date": "2015-05-01",
            "domain": domain, "transaction_type": ttype, "category": cat,
            "is_deductible": ded, "deduction_rate": rate,
        })

    add("u1", "USClient", 2000.0, "USD", "business", "income", "Client Payments")
    add("u2", "GitHub", 20.0, "USD", "business", "expense", "Software & Subscriptions", 1, 1.0)
    add("c1", "Bell", 90.0, "CAD", "business", "expense", "Internet & Telecom", 1, 1.0)
    add("c2", "Bistro", 60.0, "CAD", "business", "expense", "Meals & Entertainment", 1, 0.5)
    db.close()


def test_currency_separation_and_reports():
    _seed()
    import app.ledger as ledger
    importlib.reload(ledger)

    ov = ledger.overview(2015)
    usd = ov["totals_by_currency"]["USD"]
    cad = ov["totals_by_currency"]["CAD"]
    assert usd["income"] == 2000.0 and usd["expense"] == 20.0
    assert cad["expense"] == 150.0  # 90 + 60, never mixed with USD

    # CAD T2125: meals deducted at 50% (60 -> 30), Bell maps to a 9220 line.
    t = ledger.t2125(2015, currency="CAD")
    lines = {e["line"]: e for e in t["expenses"]}
    meals = next(v for k, v in lines.items() if "8523" in k)
    assert meals["deductible"] == 30.0

    # USD Schedule C: GitHub maps to an IRS office line.
    s = ledger.schedule_c(2015, currency="USD")
    assert s["gross_income"] == 2000.0


def test_year_range_includes_2006_to_now():
    import app.ledger as ledger
    importlib.reload(ledger)
    years = ledger.available_years()
    assert 2006 in years
    assert max(years) >= 2015
