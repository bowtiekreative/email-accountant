---
name: financial-categorization
description: "AI-driven transaction categorization — personal vs business, income vs expense, and tax category mapping. Rule engine with ML-assisted classification for ambiguous transactions."
domain: financial
tags:
  - categorization
  - personal-vs-business
  - tax-categories
  - income-expense
  - classification
---

# Financial Categorization Engine

## Overview

Classifies every financial transaction (email, receipt, invoice) into a structured taxonomy: **Personal vs Business**, **Income vs Expense**, and granular **Tax/Spending categories**. Uses a rule engine for known merchants and pattern matching for unknowns, with optional LLM-based classification for edge cases.

## Category Taxonomy

```
ALL TRANSACTIONS
├── INCOME (money received)
│   ├── BUSINESS INCOME
│   │   ├── Client Payments
│   │   ├── Product/Service Sales
│   │   ├── Consulting Fees
│   │   ├── Royalties & Licensing
│   │   ├── Affiliate Income
│   │   └── Refunds/Credits Received
│   └── PERSONAL INCOME
│       ├── Employment Salary
│       ├── Tax Refunds
│       ├── Gifts Received
│       ├── Investment Income
│       └── Transfer from Savings
│
└── EXPENSES (money spent)
    ├── BUSINESS EXPENSES
    │   ├── Software & Subscriptions
    │   ├── Equipment & Hardware
    │   ├── Marketing & Advertising
    │   ├── Professional Services
    │   ├── Travel & Meals (50% ded.)
    │   ├── Office Supplies
    │   ├── Internet & Telecom
    │   ├── Home Office Deduction
    │   ├── Education & Training
    │   └── Insurance
    └── PERSONAL EXPENSES
        ├── Housing & Rent
        ├── Groceries
        ├── Utilities
        ├── Entertainment
        ├── Personal Transport
        ├── Healthcare
        ├── Dining Out
        ├── Shopping
        └── Transfers to Savings
```

## Rule Engine

### Known Merchant → Category Mapping

```python
MERCHANT_CATEGORIES = {
    # Business software
    'slack': ('business', 'expense', 'Software & Subscriptions'),
    'github': ('business', 'expense', 'Software & Subscriptions'),
    'notion': ('business', 'expense', 'Software & Subscriptions'),
    'figma': ('business', 'expense', 'Software & Subscriptions'),
    'hostinger': ('business', 'expense', 'Internet & Telecom'),
    'digitalocean': ('business', 'expense', 'Internet & Telecom'),
    'aws': ('business', 'expense', 'Internet & Telecom'),
    'google cloud': ('business', 'expense', 'Internet & Telecom'),
    'cloudflare': ('business', 'expense', 'Internet & Telecom'),
    'sendgrid': ('business', 'expense', 'Marketing & Advertising'),
    'hubspot': ('business', 'expense', 'Marketing & Advertising'),
    'mailchimp': ('business', 'expense', 'Marketing & Advertising'),
    'canva': ('business', 'expense', 'Software & Subscriptions'),
    'adobe': ('business', 'expense', 'Software & Subscriptions'),
    
    # Income
    'stripe': ('business', 'income', 'Client Payments'),
    'paypal': None,  # Ambiguous — check sender context
    'square': ('business', 'income', 'Client Payments'),
    'upwork': ('business', 'income', 'Consulting Fees'),
    'fiverr': ('business', 'income', 'Consulting Fees'),
    
    # Personal
    'netflix': ('personal', 'expense', 'Entertainment'),
    'spotify': ('personal', 'expense', 'Entertainment'),
    'disney+': ('personal', 'expense', 'Entertainment'),
    'hulu': ('personal', 'expense', 'Entertainment'),
    'uber': None,  # Ambiguous — need to check date/time context
    'lyft': None,
    'airbnb': None,  # Could be business travel or personal
    'amazon': None,  # Heavily ambiguous — check line items
    'doordash': ('personal', 'expense', 'Dining Out'),
    'ubereats': ('personal', 'expense', 'Dining Out'),
    'walmart': ('personal', 'expense', 'Shopping'),
    'costco': None,  # Could be business or personal
}
```

### Ambiguity Resolution

```python
def classify_transaction(merchant, amount, date, day_of_week, description='', line_items=None):
    """
    Classify a transaction using rules + context clues.
    Returns (domain, type, category, confidence).
    """
    # 1. Try direct merchant match
    if merchant and merchant.lower() in MERCHANT_CATEGORIES:
        result = MERCHANT_CATEGORIES[merchant.lower()]
        if result is not None:
            return (*result, 0.95)
    
    # 2. Keyword matching on description
    business_keywords = [
        'invoice', 'client payment', 'consulting', 'freelance',
        'contractor', 'business expense', 'office', 'domain',
        'hosting', 'subscription', 'advertising', 'marketing'
    ]
    personal_keywords = [
        'personal', 'grocery', 'gas', 'entertainment', 'restaurant'
    ]
    
    desc_lower = description.lower()
    for kw in business_keywords:
        if kw in desc_lower:
            return ('business', 'expense', 'uncategorized-business', 0.7)
    for kw in personal_keywords:
        if kw in desc_lower:
            return ('personal', 'expense', 'uncategorized-personal', 0.7)
    
    # 3. Day-of-week heuristic
    if day_of_week in (6, 7) and amount < 200:  # Weekend, small amount
        return ('personal', 'expense', 'Entertainment', 0.5)
    if day_of_week in (1, 2, 3, 4, 5) and amount > 500 and 'business' in description.lower():
        return ('business', 'expense', 'uncategorized-business', 0.5)
    
    # 4. Amount heuristic
    if amount < 30:
        return ('personal', 'expense', 'Miscellaneous', 0.4)
    
    return ('unknown', 'unknown', 'uncategorized', 0.0)
```

## LLM-Assisted Classification

For ambiguous or low-confidence results, use an LLM:

```python
PROMPT = """Classify this financial transaction:
- Merchant: {merchant}
- Amount: ${amount}
- Date: {date}
- Description: {description}
- Line items: {items}

Respond ONLY with JSON:
{{
  "domain": "personal|business|unknown",
  "type": "income|expense|transfer",
  "category": "one of the tax categories listed",
  "confidence": 0.0-1.0,
  "reasoning": "one-sentence explanation"
}}"""
```

## Receipt Sub-Classification

When OCR extracts line items, classify each line:

```python
def classify_line_items(items):
    """Classify individual receipt line items as personal or business."""
    business_indicators = ['office', 'software', 'domain', 'hosting', 'software license',
                          'printer', 'toner', 'paper', 'shipping', 'web', 'server']
    personal_indicators = ['food', 'drink', 'snack', 'entertainment', 'grocery', 'toy']
    
    for item in items:
        name = item.get('description', '').lower()
        if any(kw in name for kw in business_indicators):
            item['classification'] = 'business'
        elif any(kw in name for kw in personal_indicators):
            item['classification'] = 'personal'
        else:
            item['classification'] = 'unknown'
    return items


def is_primarily_business(items):
    """Determine if a receipt is primarily business based on line items."""
    biz_items = sum(1 for i in items if i.get('classification') == 'business')
    pers_items = sum(1 for i in items if i.get('classification') == 'personal')
    if biz_items > pers_items:
        return True
    elif pers_items > biz_items:
        return False
    return None  # Split — user decision needed
```

## Tax Category Mapping (IRS Schedule C)

| Category | IRS Line | Examples |
|---|---|---|
| Advertising | Line 8 | Google Ads, Facebook Ads, flyers |
| Contract Labor | Line 11 | Freelancers, 1099 contractors |
| Depletion | Line 12 | Resource extraction |
| Depreciation | Line 13 | Equipment, vehicles over threshold |
| Employee Benefits | Line 14 | Health insurance premiums |
| Insurance | Line 15 | Business liability, professional |
| Interest/Mortgage | Line 16 | Business loan interest |
| Legal/Professional | Line 17 | Lawyer, accountant fees |
| Office Expense | Line 18 | Supplies, postage, software |
| Pension/Profit-Sharing | Line 19 | Retirement contributions |
| Rent/Lease | Line 20 | Office rent, equipment lease |
| Repairs/Maintenance | Line 21 | Equipment repairs, maintenance |
| Supplies | Line 22 | Office supplies, materials |
| Taxes/Licenses | Line 23 | Business licenses, permits |
| Travel/Gifts | Line 24a | Business travel, client gifts |
| Meals/Entertainment | Line 24b | Client meals (50% deductible) |
| Utilities | Line 25 | Internet, phone, electricity |
| Other Expenses | Line 27a | Everything else |

## GOTCHAs

- **Stripe/PayPal is bi-directional**: money flowing IN = income, money flowing OUT = expense. Always check the direction before classifying
- **Amazon is the hardest**: a single order can mix personal and business items. Best handled by line-item splitting
- **PayPal ambiguous sender**: `@paypal.com` emails can be payments to you or from you. Check the `type` field in the email body
- **Costco/Sam's Club**: bulk stores serve both personal and business — rely on line items
- **Venmo/Zelle/CashApp**: these are peer-to-peer — context from memo/description is critical
- **Meals:** 50% tax deductible for business meals; personal meals are 0% deductible. Track separately
- **Annual subscriptions**: classify at time of purchase, not as monthly. If paid yearly, it's one expense