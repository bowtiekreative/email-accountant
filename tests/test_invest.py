"""Investment calculators + advice engine."""
import importlib
from datetime import datetime, timedelta


def test_compound_growth_matches_formula():
    import app.invest as invest
    importlib.reload(invest)
    # $0 principal, $100/mo, 10%/yr, 10y. Closed-form annuity FV.
    res = invest.compound_growth(0, 100, 0.10, 10)
    r = 0.10 / 12
    n = 120
    expected = 100 * (((1 + r) ** n - 1) / r)
    assert abs(res["future_value"] - expected) < 1.0
    assert res["total_contributed"] == 12000.0
    assert len(res["series"]) == 10


def test_fire_number():
    import app.invest as invest
    importlib.reload(invest)
    fire = invest.fire_number(40000, 0.04)
    assert fire["fire_number"] == 1_000_000.0


def test_years_to_target_reachable_and_not():
    import app.invest as invest
    importlib.reload(invest)
    assert invest.years_to_target(0, 0, 100) == 0.0
    # Unreachable: target huge, no contributions, no principal.
    assert invest.years_to_target(1_000_000, 0, 0) is None


def test_wealth_advice_from_cashflow():
    from db.database import EmailAccountantDB, init_sqlite
    init_sqlite()
    db = EmailAccountantDB()
    base = datetime.now().replace(day=10)
    for i in range(12):
        d = base - timedelta(days=30 * i)
        for tag, amt, ttype, dom, cat in [
            ("inc", 4000.0, "income", "business", "Client Payments"),
            ("din", 300.0, "expense", "personal", "Dining Out"),
        ]:
            eid = db.insert_email({
                "gmail_message_id": f"{tag}{i}", "from_header": "X <x@x.com>",
                "subject": tag, "email_date": d.isoformat(), "snippet": "x",
                "from_email": "x@x.com", "from_name": "X", "email_status": "pending",
            })
            db.insert_transaction({
                "email_id": eid, "email_subject": tag, "email_date": d.isoformat(),
                "merchant_name": tag, "amount": amt, "currency": "USD",
                "domain": dom, "transaction_type": ttype, "category": cat,
            })
    db.close()

    import app.invest as invest
    importlib.reload(invest)
    adv = invest.wealth_advice("USD")
    assert adv["cashflow"]["monthly_surplus"] > 0
    assert adv["recommended_monthly_investment"] > 0
    assert any("Dining Out" in t["title"] for t in adv["tips"])
    assert adv["fire"]["fire_number"] > 0
