from pipeline.processor import classify_merchant, canonical_category


def cat(name, amount=25.0, frm=""):
    return classify_merchant(name, name, amount, frm)[2]


def test_granular_merchant_categories():
    assert cat("Starbucks") == "Coffee Shops"
    assert cat("Loblaws") == "Groceries"
    assert cat("Shell") == "Fuel & Gas (Personal)"
    assert cat("Air Canada") == "Travel & Vacation"
    assert cat("QuickBooks") == "Software & Subscriptions"
    assert cat("Google Ads") == "Online Ads"


def test_most_specific_match_wins():
    # "uber eats" must not be classified as plain "uber"
    assert cat("UBER EATS") in ("Food Delivery", "Dining Out")
    assert cat("Uber") == "Personal Transport"
    # "booking.com" must not match the short 'king' app key
    assert cat("booking.com") == "Travel & Vacation"


def test_unknown_merchant_is_low_confidence():
    domain, tx_type, category, conf = classify_merchant("Zxqw Llc", "Zxqw Llc", 25.0, "")
    assert conf < 0.5  # flagged for review, not confidently wrong


def test_canonicalization_maps_legacy_names():
    assert canonical_category("Transport") == "Personal Transport"
    assert canonical_category("Marketing") == "Marketing & Advertising"
    assert canonical_category("Miscellaneous Income") == "Other Personal Income"
    assert canonical_category("unresolved") == "Uncategorized"
    assert canonical_category(None) == "Uncategorized"


def test_canadian_merchant_via_sender():
    d, t, c, conf = classify_merchant("MoneyMart", "MoneyMart", 10.0, "serviceonline@moneymart.ca")
    assert c == "Loans & Financing"
