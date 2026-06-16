"""Learn-from-edits: corrections become rules and apply to past transactions."""
import importlib
from datetime import datetime, timedelta


def _seed_mystery():
    from db.database import EmailAccountantDB, init_sqlite
    init_sqlite()
    db = EmailAccountantDB()
    base = datetime.now().replace(day=10)
    for i in range(4):
        d = base - timedelta(days=30 * i)
        eid = db.insert_email({
            "gmail_message_id": f"mc{i}", "from_header": "MysteryCorp <x@m.com>",
            "subject": "MysteryCorp", "email_date": d.isoformat(), "snippet": "x",
            "from_email": "x@m.com", "from_name": "MysteryCorp", "email_status": "pending",
        })
        db.insert_transaction({
            "email_id": eid, "email_subject": "MysteryCorp", "email_date": d.isoformat(),
            "merchant_name": "MysteryCorp", "amount": 30.0, "currency": "USD",
            "domain": "personal", "transaction_type": "expense",
            "category": "Uncategorized", "reviewed": 0, "needs_review": 1,
        })
    db.close()


def test_correction_backfills_history_and_records_rule():
    _seed_mystery()
    import app.learning as learning
    importlib.reload(learning)

    res = learning.learn_from_edit(
        "MysteryCorp",
        {"category": "Software & Subscriptions", "domain": "business", "transaction_type": "expense"},
    )
    assert res["learned"] is True
    assert res["updated_past"] == 4  # all unreviewed past txns updated

    rules = {r["merchant_label"]: r for r in learning.list_rules()}
    assert rules["MysteryCorp"]["category"] == "Software & Subscriptions"


def test_classifier_uses_learned_rule():
    _seed_mystery()
    import app.learning as learning
    importlib.reload(learning)
    learning.learn_from_edit("MysteryCorp", {"category": "Software & Subscriptions",
                                             "domain": "business", "transaction_type": "expense"})

    from pipeline.processor import classify_merchant, load_learned_rules
    load_learned_rules(force=True)
    domain, tx_type, category, conf = classify_merchant("MysteryCorp", "MysteryCorp", 30.0, "")
    assert (domain, category) == ("business", "Software & Subscriptions")
    assert conf >= 0.95
