"""Tests for net-worth tracking."""
import importlib

from db.database import init_sqlite


def _nw():
    init_sqlite()  # ensure the main ledger DB exists
    import app.networth as networth
    importlib.reload(networth)
    # Isolate: tests share one main DB, so start each from a clean slate.
    conn = networth._conn()
    conn.execute("DELETE FROM networth_snapshots")
    conn.execute("DELETE FROM networth_accounts")
    conn.commit()
    conn.close()
    return networth


def test_summary_assets_minus_liabilities():
    nw = _nw()
    nw.add_account("TFSA", "asset", "investment", "CAD", balance=15000)
    nw.add_account("Savings", "asset", "savings", "CAD", balance=8000)
    nw.add_account("Visa", "liability", "credit_card", "CAD", balance=2500)

    s = nw.summary("CAD")
    assert s["assets"] == 23000.0
    assert s["liabilities"] == 2500.0
    assert s["net_worth"] == 20500.0


def test_history_carries_forward_snapshots():
    nw = _nw()
    acct = nw.add_account("Brokerage", "asset", "investment", "USD", balance=None)
    nw.record_snapshot(acct["id"], 10000, as_of="2025-01-15")
    nw.record_snapshot(acct["id"], 12000, as_of="2025-03-15")

    hist = nw.history("USD")
    months = {h["month"]: h["net_worth"] for h in hist}
    # February carries January's balance forward; March reflects the new one.
    assert months["2025-01"] == 10000.0
    assert months["2025-02"] == 10000.0
    assert months["2025-03"] == 12000.0


def test_projection_compounds_from_current_net_worth():
    nw = _nw()
    nw.add_account("TFSA", "asset", "investment", "USD", balance=20000)
    proj = nw.projection("USD", annual_rate=0.08, years=20)
    assert proj["starting_net_worth"] == 20000.0
    # Even with zero surplus, 20k compounding at 8% for 20y must grow a lot.
    assert proj["future_value"] > 80000
