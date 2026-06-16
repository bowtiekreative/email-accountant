from pipeline.processor import detect_currency


def test_explicit_usd_token():
    assert detect_currency("Total $49.99 USD", "receipts@stripe.com") == "USD"


def test_explicit_cad_token():
    assert detect_currency("Total 90.00 CAD", "x@example.com") == "CAD"
    assert detect_currency("Invoice C$200.00", "x@example.com") == "CAD"


def test_ca_sender_domain_implies_cad():
    assert detect_currency("Your receipt $25.00", "orders@shop.ca") == "CAD"


def test_canadian_merchant_hint_implies_cad():
    assert detect_currency("Your receipt $25.00", "noreply@rogers.com", "Rogers") == "CAD"


def test_defaults_to_usd():
    assert detect_currency("Payment $100", "billing@hostinger.com", "Hostinger") == "USD"
