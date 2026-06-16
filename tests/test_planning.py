"""Tests for the budgeting + planning suite."""
import importlib
from datetime import datetime, timedelta


def _seed_recurring():
    from db.database import EmailAccountantDB, init_sqlite
    init_sqlite()
    db = EmailAccountantDB()
    base = datetime.now().replace(day=5)

    def add(gid, merch, amt, cur, cat, date, ttype="expense", domain="personal"):
        eid = db.insert_email({
            "gmail_message_id": gid, "from_header": f"{merch} <x@{merch}.com>",
            "subject": merch, "email_date": date.isoformat(), "snippet": "x",
            "from_email": f"x@{merch}.com", "from_name": merch, "email_status": "pending",
        })
        db.insert_transaction({
            "email_id": eid, "email_subject": merch, "email_date": date.isoformat(),
            "merchant_name": merch, "amount": amt, "currency": cur,
            "transaction_date": date.date().isoformat(), "domain": domain,
            "transaction_type": ttype, "category": cat,
        })

    for i in range(6):
        d = base - timedelta(days=30 * i)
        add(f"nf{i}", "Netflix", 16.99, "CAD", "Entertainment", d)
        add(f"gh{i}", "GitHub", 10.00, "USD", "Software & Subscriptions", d, domain="business")
    db.close()


def _planning():
    import app.planning as planning
    importlib.reload(planning)
    return planning


def test_subscription_detection():
    _seed_recurring()
    planning = _planning()
    subs = planning.subscriptions()
    merchants = {s["merchant"]: s for s in subs["subscriptions"]}
    assert "Netflix" in merchants
    assert merchants["Netflix"]["frequency"] == "monthly"
    assert merchants["Netflix"]["currency"] == "CAD"
    assert subs["monthly_burn_by_currency"]["CAD"] > 0


def test_budget_set_and_recommend():
    _seed_recurring()
    planning = _planning()
    planning.set_budget("Entertainment", 10.0, currency="CAD")
    budgets = {b["category"]: b for b in planning.list_budgets() if b["currency"] == "CAD"}
    assert budgets["Entertainment"]["monthly_limit"] == 10.0

    recs = planning.budget_recommendations(currency="CAD")["recommendations"]
    cats = {r["category"] for r in recs}
    assert "Entertainment" in cats


def test_yearly_plan_projects_expense():
    _seed_recurring()
    planning = _planning()
    plan = planning.yearly_plan(datetime.now().year, currency="CAD")
    assert plan["actual_expense"] > 0
    assert plan["projected_expense"] >= plan["actual_expense"]


def test_reminders_build_without_smtp():
    _seed_recurring()
    import app.reminders as reminders
    importlib.reload(reminders)
    planning = _planning()
    planning.set_budget("Entertainment", 1.0, currency="CAD")  # force an overrun
    items = reminders.build_reminders()
    assert any(r["type"] in ("budget_overrun", "budget_warning") for r in items)
