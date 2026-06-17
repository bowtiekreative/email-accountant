"""Connector + routing tests. HTTP is mocked — no live services needed."""

from integrations import akaunting, firefly, orchestrator
from integrations.normalize import NormalizedTxn, from_ledger_row


def _txn(**kw):
    base = dict(
        source_id="ledger:email_accountant_2025:42", date="2025-05-01",
        amount=49.99, currency="USD", direction="expense", domain="personal",
        merchant="Netflix", category="Entertainment",
    )
    base.update(kw)
    return NormalizedTxn(**base)


def test_normalize_from_ledger_row():
    txn = from_ledger_row({
        "id": 7, "transaction_date": "2025-03-04", "email_date": "2025-03-04T10:00:00",
        "amount": -50.0, "currency": "cad", "transaction_type": "expense",
        "domain": "business", "merchant_name": "Bell", "category": "Internet & Telecom",
    }, db_stem="email_accountant_2025")
    assert txn.source_id == "ledger:email_accountant_2025:7"
    assert txn.amount == 50.0  # absolute value
    assert txn.currency == "CAD"  # upper-cased


def test_firefly_expense_is_withdrawal(monkeypatch):
    monkeypatch.setenv("FIREFLY_TOKEN", "t")
    monkeypatch.setenv("FIREFLY_ENABLED", "true")
    captured = {}

    def fake(method, url, **kw):
        captured["json"] = kw.get("json")
        return {"data": {"id": "99"}}

    monkeypatch.setattr(firefly, "request", fake)
    res = firefly.create_transaction(_txn())
    assert res["firefly_id"] == "99"
    split = captured["json"]["transactions"][0]
    assert split["type"] == "withdrawal"
    assert split["source_name"] == "Checking account"
    assert split["destination_name"] == "Netflix"
    assert split["amount"] == "49.99"
    assert "personal" in split["tags"]


def test_firefly_income_is_deposit(monkeypatch):
    monkeypatch.setenv("FIREFLY_TOKEN", "t")
    captured = {}
    monkeypatch.setattr(firefly, "request",
                        lambda m, u, **k: captured.update(json=k.get("json")) or {"data": {"id": "1"}})
    firefly.create_transaction(_txn(direction="income", merchant="ClientCo"))
    split = captured["json"]["transactions"][0]
    assert split["type"] == "deposit"
    assert split["source_name"] == "ClientCo"
    assert split["destination_name"] == "Checking account"


def test_akaunting_resolves_category_and_contact(monkeypatch):
    monkeypatch.setenv("AKAUNTING_TOKEN", "t")
    monkeypatch.setenv("AKAUNTING_ENABLED", "true")
    calls = []

    def fake(method, url, **kw):
        calls.append((method, url))
        if url.endswith("/api/categories") and method == "GET":
            return {"data": []}
        if url.endswith("/api/categories") and method == "POST":
            return {"data": {"id": 7}}
        if url.endswith("/api/contacts") and method == "GET":
            return {"data": []}
        if url.endswith("/api/contacts") and method == "POST":
            return {"data": {"id": 3}}
        if url.endswith("/api/transactions"):
            return {"data": {"id": 55, "payload": kw.get("json")}}
        return {"data": {}}

    monkeypatch.setattr(akaunting, "request", fake)
    res = akaunting.create_transaction(_txn(direction="income", domain="business", merchant="ClientCo"))
    assert res["akaunting_id"] == 55
    assert res["type"] == "income"


def test_orchestrator_routes_personal_to_firefly(monkeypatch):
    monkeypatch.setenv("FIREFLY_TOKEN", "t")
    monkeypatch.setenv("FIREFLY_ENABLED", "true")
    monkeypatch.setenv("AKAUNTING_ENABLED", "false")
    monkeypatch.setenv("PAPERLESS_ENABLED", "false")
    monkeypatch.setenv("STRAPI_ENABLED", "false")
    monkeypatch.setattr(firefly, "request", lambda m, u, **k: {"data": {"id": "77"}})

    res = orchestrator.route_transaction(_txn(domain="personal"))
    assert res["routed_to"] == "firefly"
    assert res["status"] == "synced"
    assert res["actions"]["firefly"]["firefly_id"] == "77"


def test_orchestrator_routes_business_to_akaunting(monkeypatch):
    monkeypatch.setenv("AKAUNTING_TOKEN", "t")
    monkeypatch.setenv("AKAUNTING_ENABLED", "true")
    monkeypatch.setenv("FIREFLY_ENABLED", "false")
    monkeypatch.setenv("PAPERLESS_ENABLED", "false")
    monkeypatch.setenv("STRAPI_ENABLED", "false")
    monkeypatch.setattr(akaunting, "request",
                        lambda m, u, **k: {"data": {"id": 5} if "transactions" in u else []})

    res = orchestrator.route_transaction(_txn(domain="business", direction="expense"))
    assert res["routed_to"] == "akaunting"
    assert res["status"] == "synced"
