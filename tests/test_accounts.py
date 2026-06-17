"""Tests for the shared multi-account config and per-account filtering."""
import importlib


def _accounts():
    import accounts
    importlib.reload(accounts)
    return accounts


def test_seeds_default_accounts():
    accounts = _accounts()
    labels = [a["label"] for a in accounts.load()["accounts"]]
    # The primary account must be present (the bug we fixed in the full scan).
    assert "personal" in labels
    assert len(labels) >= 7


def test_add_imap_account_sets_host():
    accounts = _accounts()
    accounts.add_account("work", "me@outlook.com", provider="outlook", password="secret")
    pub = {a["label"]: a for a in accounts.public_view()}
    assert pub["work"]["provider"] == "outlook"
    assert pub["work"]["imap_host"] == "outlook.office365.com"
    assert pub["work"]["has_password"] is True


def test_public_view_never_leaks_password():
    accounts = _accounts()
    accounts.add_account("secretacct", "x@y.com", provider="gmail", password="topsecret")
    for a in accounts.public_view():
        assert "password" not in a


def test_get_accounts_resolves_password():
    accounts = _accounts()
    accounts.add_account("resolver", "x@y.com", provider="gmail", password="pw123")
    resolved = {a["label"]: a for a in accounts.get_accounts()}
    assert resolved["resolver"]["password"] == "pw123"


def test_duplicate_label_rejected():
    accounts = _accounts()
    accounts.add_account("dupe", "a@b.com")
    try:
        accounts.add_account("dupe", "c@d.com")
        assert False, "expected ValueError"
    except ValueError:
        pass
