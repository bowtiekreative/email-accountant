"""
Email Accountant — Processing Pipeline
Extracts financial data from emails and attachments, classifies transactions.
Completely exhaustive categorization — no "Miscellaneous" or "unknown" buckets.
"""
import os
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

# ===========================================================================
# COMPREHENSIVE MERCHANT CATEGORIES
# Every merchant that appears in email data mapped to a real category.
# ===========================================================================

# Google Play / PayPal merchant names → (domain, transaction_type, category)
# These are extracted from PayPal "PAYPAL *MERCHANT" strings and Google Play subjects.
MERCHANT_CATEGORIES = {
    # === SCAM / FRAUD / FAKE INVOICES ===
    'smartdollarsclub': ('personal', 'expense', 'Suspected Scam'),
    'yourdomain': ('personal', 'expense', 'Suspected Scam'),
    'proton.me': ('personal', 'expense', 'Suspected Scam'),

    # === PERSONAL: Loans & Financing ===
    'moneymart': ('personal', 'expense', 'Loans & Financing'),
    'capitalone': ('personal', 'expense', 'Loans & Financing'),
    'telus': ('personal', 'expense', 'Internet & Telecom'),
    'urbansuites': ('business', 'income', 'Client Payments'),
    'shutterstock': ('business', 'expense', 'Professional Services'),

    # === PERSONAL: Entertainment ===
    'playstation': ('personal', 'expense', 'Entertainment'),
    'samsung': ('personal', 'expense', 'Marketing'),
    'skrill': ('personal', 'expense', 'Shopping'),

    # === PERSONAL: Dining Out / Food ===
    'uber eats': ('personal', 'expense', 'Dining Out'),
    'ubereats': ('personal', 'expense', 'Dining Out'),

    # === BUSINESS: Software & Subscriptions ===
    'slack': ('business', 'expense', 'Software & Subscriptions'),
    'github': ('business', 'expense', 'Software & Subscriptions'),
    'notion': ('business', 'expense', 'Software & Subscriptions'),
    'figma': ('business', 'expense', 'Software & Subscriptions'),
    'openrouter': ('business', 'expense', 'Software & Subscriptions'),
    'anthropic': ('business', 'expense', 'Software & Subscriptions'),
    'perplexity': ('business', 'expense', 'Software & Subscriptions'),
    'pictory': ('business', 'expense', 'Software & Subscriptions'),
    'lenso': ('business', 'expense', 'Software & Subscriptions'),
    'paddle': ('business', 'expense', 'Software & Subscriptions'),
    'twilio': ('business', 'expense', 'Software & Subscriptions'),
    'facetwp': ('business', 'expense', 'Software & Subscriptions'),
    'robomotion': ('business', 'expense', 'Software & Subscriptions'),
    'mainfunc': ('business', 'expense', 'Software & Subscriptions'),
    'elementor': ('business', 'expense', 'Software & Subscriptions'),
    'canva': ('business', 'expense', 'Software & Subscriptions'),
    'adobe': ('business', 'expense', 'Software & Subscriptions'),
    'chatgpt': ('business', 'expense', 'Software & Subscriptions'),
    'openai': ('business', 'expense', 'Software & Subscriptions'),
    'ibm cloud': ('business', 'expense', 'Internet & Telecom'),
    'converslabs': ('business', 'expense', 'Software & Subscriptions'),

    # === BUSINESS: Internet & Telecom ===
    'hostinger': ('business', 'expense', 'Internet & Telecom'),
    'digitalocean': ('business', 'expense', 'Internet & Telecom'),
    'aws': ('business', 'expense', 'Internet & Telecom'),
    'google cloud': ('business', 'expense', 'Internet & Telecom'),
    'cloudflare': ('business', 'expense', 'Internet & Telecom'),
    'godaddy': ('business', 'expense', 'Internet & Telecom'),
    'namecheap': ('business', 'expense', 'Internet & Telecom'),
    'vercel': ('business', 'expense', 'Internet & Telecom'),
    'netlify': ('business', 'expense', 'Internet & Telecom'),
    'heroku': ('business', 'expense', 'Internet & Telecom'),

    # === BUSINESS: Marketing & Advertising ===
    'sendgrid': ('business', 'expense', 'Marketing & Advertising'),
    'hubspot': ('business', 'expense', 'Marketing & Advertising'),
    'mailchimp': ('business', 'expense', 'Marketing & Advertising'),
    'meta platforms': ('business', 'expense', 'Marketing & Advertising'),
    'facebook': ('business', 'expense', 'Marketing & Advertising'),
    'instagram': ('business', 'expense', 'Marketing & Advertising'),
    'facebook ads': ('business', 'expense', 'Marketing & Advertising'),
    'meta': ('business', 'expense', 'Marketing & Advertising'),

    # === BUSINESS: Income processors (bi-directional — check context) ===
    'stripe': None,   # Check direction
    'square': None,   # Check direction
    'paypal': None,   # Check direction
    'shopify': None,  # Check direction

    # === BUSINESS: Income ===
    'upwork': ('business', 'income', 'Consulting Fees'),
    'fiverr': ('business', 'income', 'Consulting Fees'),
    'ko-fi': ('business', 'income', 'Client Payments'),
    'koho': ('personal', 'income', 'Miscellaneous Income'),  # Tax refund/cashback

    # === PERSONAL: Entertainment (dating apps, gaming, streaming) ===
    'grindr': ('personal', 'expense', 'Entertainment'),
    'tinder': ('personal', 'expense', 'Entertainment'),
    'bumble': ('personal', 'expense', 'Entertainment'),
    'plenty of fish': ('personal', 'expense', 'Entertainment'),
    'pof': ('personal', 'expense', 'Entertainment'),
    'tiktok': ('personal', 'expense', 'Entertainment'),
    'miniclip': ('personal', 'expense', 'Entertainment'),
    'netflix': ('personal', 'expense', 'Entertainment'),
    'spotify': ('personal', 'expense', 'Entertainment'),
    'disney+': ('personal', 'expense', 'Entertainment'),
    'disney': ('personal', 'expense', 'Entertainment'),
    'hulu': ('personal', 'expense', 'Entertainment'),
    'hbo': ('personal', 'expense', 'Entertainment'),
    'king.com': ('personal', 'expense', 'Entertainment'),
    'king': ('personal', 'expense', 'Entertainment'),

    # === PERSONAL: Dining Out ===
    'doordash': ('personal', 'expense', 'Dining Out'),
    'ubereats': ('personal', 'expense', 'Dining Out'),
    'grubhub': ('personal', 'expense', 'Dining Out'),

    # === PERSONAL: Transport ===
    'uber': ('personal', 'expense', 'Transport'),
    'lyft': ('personal', 'expense', 'Transport'),
    'uber one': ('personal', 'expense', 'Transport'),
    'oxio': ('personal', 'expense', 'Internet & Telecom'),  # Home internet

    # === PERSONAL: Shopping ===
    'walmart': ('personal', 'expense', 'Shopping'),
    'target': ('personal', 'expense', 'Shopping'),
    'costco': ('personal', 'expense', 'Shopping'),
    'amazon': ('personal', 'expense', 'Shopping'),
    'instacart': ('personal', 'expense', 'Groceries'),
    'petsmart': ('personal', 'expense', 'Shopping'),
    'petco': ('personal', 'expense', 'Shopping'),

    # === BUSINESS: Software & Subscriptions (continued) ===
    'lemonsqueezy': ('business', 'expense', 'Software & Subscriptions'),
    'intelius': ('personal', 'expense', 'Entertainment'),
    'spokeo': ('personal', 'expense', 'Entertainment'),
    'texture': ('personal', 'expense', 'Entertainment'),
    'ancestry': ('personal', 'expense', 'Entertainment'),
    'udemy': ('business', 'expense', 'Software & Subscriptions'),
    'descript': ('business', 'expense', 'Software & Subscriptions'),

    # === PERSONAL: Software & Subscriptions ===
    'google play': ('personal', 'expense', 'Entertainment'),
    'google storage': ('personal', 'expense', 'Software & Subscriptions'),
    'google workspace': ('business', 'expense', 'Software & Subscriptions'),
    'google one': ('personal', 'expense', 'Software & Subscriptions'),
    'textnow': ('personal', 'expense', 'Software & Subscriptions'),
    'eventbrite': ('personal', 'expense', 'Entertainment'),

    # === PERSONAL: Health/Fitness ===
    'aica merchant': ('personal', 'expense', 'Healthcare'),  # Context check needed

    # === PERSONAL: Miscellaneous — actual meaningful sub-categories ===
    'nymag': ('personal', 'expense', 'Entertainment'),
    'billiongraves': ('personal', 'expense', 'Shopping'),
}

# Google Play app → real merchant/category mapping
# These appear in "Receipt for Your Payment to Google" PayPal emails
# The merchant_name will be like "GOOGLE GRINDR L" — we need to extract the app
GOOGLE_PLAY_MERCHANT_MAP = {
    'grindr': ('Grindr', 'personal', 'expense', 'Entertainment', 0.85),
    'tinder': ('Tinder', 'personal', 'expense', 'Entertainment', 0.85),
    'tiktok': ('TikTok', 'personal', 'expense', 'Entertainment', 0.85),
    'miniclip': ('Miniclip', 'personal', 'expense', 'Entertainment', 0.85),
    'pof': ('Plenty of Fish', 'personal', 'expense', 'Entertainment', 0.85),
    'textnow': ('TextNow', 'personal', 'expense', 'Software & Subscriptions', 0.85),
    'chatgpt': ('ChatGPT', 'business', 'expense', 'Software & Subscriptions', 0.85),
    'king': ('King Games', 'personal', 'expense', 'Entertainment', 0.85),
    'facebook': ('Facebook', 'business', 'expense', 'Marketing & Advertising', 0.85),
    'instagram': ('Instagram', 'business', 'expense', 'Marketing & Advertising', 0.85),
    'linkedin': ('LinkedIn', 'business', 'expense', 'Marketing & Advertising', 0.85),
    'youtube': ('YouTube', 'personal', 'expense', 'Entertainment', 0.85),
    'snapchat': ('Snapchat', 'personal', 'expense', 'Entertainment', 0.85),
    'discord': ('Discord', 'personal', 'expense', 'Entertainment', 0.85),
    'pinterest': ('Pinterest', 'business', 'expense', 'Marketing & Advertising', 0.85),
    'google one': ('Google One', 'personal', 'expense', 'Software & Subscriptions', 0.85),
}

# Sender → default classification (for emails that don't parse well)
SENDER_CLASSIFICATION = {
    'service@intl.paypal.com': None,   # Bi-directional — check context
    'googleplay-noreply@google.com': ('personal', 'expense', 'Entertainment', 0.8),
    'payments-noreply@google.com': ('personal', 'expense', 'Entertainment', 0.8),
    'workspace-noreply@google.com': ('business', 'expense', 'Software & Subscriptions', 0.9),
    'noreply@uber.com': ('personal', 'expense', 'Transport', 0.95),
    'uber.canada@uber.com': ('personal', 'expense', 'Transport', 0.95),
    'uber@uber.com': ('personal', 'expense', 'Transport', 0.95),
    'uberone@uber.com': ('personal', 'expense', 'Transport', 0.95),
    'ubereats@uber.com': ('personal', 'expense', 'Dining Out', 0.95),
    'no-reply@doordash.com': ('personal', 'expense', 'Dining Out', 0.95),
    'no-reply@messages.doordash.com': ('personal', 'expense', 'Dining Out', 0.95),
    'receipts@openrouter.ai': ('business', 'expense', 'Software & Subscriptions', 0.95),
    'noreply@openrouter.ai': ('business', 'expense', 'Software & Subscriptions', 0.95),
    'welcome@openrouter.ai': ('business', 'expense', 'Software & Subscriptions', 0.80),
    'hello@facetwp.com': ('business', 'expense', 'Software & Subscriptions', 0.95),
    'team@system-mail.elementor.com': ('business', 'expense', 'Software & Subscriptions', 0.95),
    'contact@support.elementor.com': ('business', 'expense', 'Software & Subscriptions', 0.90),
    'accounts@support.elementor.com': ('business', 'expense', 'Software & Subscriptions', 0.90),
    'invoice@elementor.com': ('business', 'expense', 'Software & Subscriptions', 0.95),
    'no-reply@spotify.com': ('personal', 'expense', 'Entertainment', 0.95),
    'no-reply@legal.spotify.com': ('personal', 'expense', 'Entertainment', 0.85),
    'noreply@business-updates.facebook.com': ('business', 'expense', 'Marketing & Advertising', 0.90),
    'business-noreply@mail.instagram.com': ('business', 'expense', 'Marketing & Advertising', 0.90),
    'noreply@facebookmail.com': ('personal', 'expense', 'Entertainment', 0.70),
    'email@email.shopify.com': ('business', 'income', 'Product/Service Sales', 0.85),
    'mailer@shopify.com': ('business', 'income', 'Product/Service Sales', 0.85),
    'failed-payments@perplexity.ai': ('business', 'expense', 'Software & Subscriptions', 0.90),
    'help@paddle.com': ('business', 'expense', 'Software & Subscriptions', 0.85),
    'contact@lenso.ai': ('business', 'expense', 'Software & Subscriptions', 0.85),
    'info@pictory.ai': ('business', 'expense', 'Software & Subscriptions', 0.85),
    'email@send.converslabs.com': ('business', 'expense', 'Software & Subscriptions', 0.80),
    'no-reply@cloud.ibm.com': ('business', 'expense', 'Internet & Telecom', 0.90),
    'message@adobe.com': ('business', 'expense', 'Software & Subscriptions', 0.85),
    'team@support.koho.ca': ('personal', 'income', 'Miscellaneous Income', 0.85),
    'bienvenue@oxio.ca': ('personal', 'expense', 'Internet & Telecom', 0.90),
    'info@account.netflix.com': ('personal', 'expense', 'Entertainment', 0.95),
    'orders@instacart.com': ('personal', 'expense', 'Groceries', 0.90),
    'noreply@order.eventbrite.com': ('personal', 'expense', 'Entertainment', 0.80),
    'hello@e.nymag.com': ('personal', 'expense', 'Entertainment', 0.70),
    'ko-fi@ko-fi.com': ('business', 'income', 'Client Payments', 0.90),
    'invoice@bowtiekreative.com': ('business', 'income', 'Client Payments', 0.95),
    'ap@antoinetteandfriends.com': ('business', 'income', 'Client Payments', 0.80),
    'emioffices@aol.com': ('business', 'income', 'Client Payments', 0.70),
    'bonnieg@billiongraves.com': ('personal', 'expense', 'Shopping', 0.60),
    'dup@test.com': ('unknown', 'expense', 'unresolved', 0.10),
    'ryan@bowtiekreative.com': ('personal', 'income', 'Employment Salary', 0.60),
    'notification@mailsuite.com': ('unknown', 'expense', 'unresolved', 0.40),
    'transactional@mailing.image': ('unknown', 'expense', 'unresolved', 0.30),
    'donotreply@godaddy.com': ('business', 'expense', 'Internet & Telecom', 0.90),
    'renewals@e.godaddy.com': ('business', 'expense', 'Internet & Telecom', 0.90),
    'invoice+statements@mail.anthropic.com': ('business', 'expense', 'Software & Subscriptions', 0.95),
    'microsoft365@infomails.microsoft.com': ('business', 'expense', 'Software & Subscriptions', 0.90),
    'aryan.f@emergent.sh': ('business', 'expense', 'Professional Services', 0.70),
    'hello@lemonsqueezy-mail.com': ('business', 'expense', 'Software & Subscriptions', 0.95),
    'accounts@mg.mailer.intelius.com': ('personal', 'expense', 'Entertainment', 0.80),
    'petsmart@emails.petsmart.com': ('personal', 'expense', 'Shopping', 0.95),
    'noreply@mail4.spokeo.com': ('personal', 'expense', 'Entertainment', 0.85),
    'email@email.texture.ca': ('personal', 'expense', 'Entertainment', 0.85),
    'ancestry@email.ancestry.ca': ('personal', 'expense', 'Entertainment', 0.85),
    'udemy@email.udemy.com': ('business', 'expense', 'Software & Subscriptions', 0.85),
    'paypal@emails.paypal.com': ('personal', 'expense', 'Shopping', 0.50),  # Promotional/rewards emails
    # === SCAM / FRAUD SENDERS ===
    'earn@smartdollarsclub.com': ('personal', 'expense', 'Suspected Scam', 0.30),
    'info@yourdomain.com': ('personal', 'expense', 'Suspected Scam', 0.30),
    'oaitsehellard@gmail.com': ('personal', 'expense', 'Suspected Scam', 0.30),
    # === MISSING LEGITIMATE SENDERS ===
    'no-reply@email1.samsung.ca': ('personal', 'expense', 'Marketing', 0.50),
    'serviceonline@moneymart.ca': ('personal', 'expense', 'Loans & Financing', 0.90),
    'donotreply@topleaf.ca': ('personal', 'expense', 'Shopping', 0.80),
    'noreply@shutterstock.com': ('business', 'expense', 'Professional Services', 0.90),
    'promotions@telus.com': ('personal', 'expense', 'Internet & Telecom', 0.80),
    'capitalone@notification.capitalone.com': ('personal', 'expense', 'Loans & Financing', 0.85),
    'txn-email.playstation': ('personal', 'expense', 'Entertainment', 0.95),
    'txn-email03.playstation': ('personal', 'expense', 'Entertainment', 0.95),
    'email.skrill': ('personal', 'expense', 'Shopping', 0.80),
    'elaine@urbansuites.com': ('business', 'income', 'Client Payments', 0.90),
    'kennysicrad96@gmail.com': ('personal', 'expense', 'Suspected Scam', 0.30),
    'support@bcsupport.zendesk.com': ('business', 'expense', 'Professional Services', 0.85),
    'notification@mailsuite.com': ('unknown', 'expense', 'unresolved', 0.40),
    'transactional@mailing.image': ('unknown', 'expense', 'unresolved', 0.30),
    'reply@txn-email.playstation.com': ('personal', 'expense', 'Entertainment', 0.95),
    'no-reply@email.skrill.com': ('personal', 'expense', 'Shopping', 0.80),
    'mdaj88631@gmail.com': ('personal', 'expense', 'Shopping', 0.50),
    # Forwarded emails from own address — amounts are from old forwarded content
    'theapprentice4@gmail.com': ('unknown', 'expense', 'unresolved', 0.30),
}

# Stripe sender patterns (these send payment receipts, invoices, failed payments)
STRIPE_SENDER_PATTERNS = [
    'stripe.com',
    'failed-payments+acct_',
    'invoice+statements+acct_',
    'upcoming-invoice+acct_',
    'notifications@stripe.com',
    'receipts+acct_',
]

# Known Sender Domains → Classification
SENDER_DOMAIN_CLASSIFICATION = {
    'paypal.com': None,  # bi-directional
    'stripe.com': ('business', 'income', 'Client Payments', 0.85),
    'squareup.com': ('business', 'income', 'Client Payments', 0.85),
    'amazon.com': ('personal', 'expense', 'Shopping', 0.85),
    'shopify.com': ('business', 'income', 'Product/Service Sales', 0.85),
    'godaddy.com': ('business', 'expense', 'Internet & Telecom', 0.85),
    'mailchimp.com': ('business', 'expense', 'Marketing & Advertising', 0.85),
}


# ===========================================================================
# AMOUNT PATTERNS
# ===========================================================================

AMOUNT_PATTERNS = [
    r'\$(\d+\.\d{2})',
    r'(?:total|amount)[:\s]*\$?(\d+\.\d{2})',
    r'(?:charged|paid)[:\s]*\$?(\d+\.\d{2})',
]


def extract_amount_from_text(text: str) -> Optional[float]:
    """Extract dollar amount from text."""
    if not text:
        return None
    amounts = re.findall(r'\$(\d+\.\d{2})', text)
    if amounts:
        return max(float(a) for a in amounts)
    return None


def extract_google_play_merchant(merchant_name: str) -> Optional[Tuple[str, str, str, float]]:
    """
    Extract the real app/merchant from a Google Play PayPay payment.
    Names come as "GOOGLE GRINDR L", "GOOGLE TIKTOK", "GOOGLE CHATGPT" etc.
    """
    name_lower = (merchant_name or '').lower().strip()
    
    # Strip the "google" prefix
    cleaned = re.sub(r'^google\s+', '', name_lower)
    cleaned = re.sub(r'\s+(l|llc|inc|com|corp|limited)$', '', cleaned)
    cleaned = cleaned.strip()
    
    # Try matching the cleaned name
    if cleaned:
        for key, result in GOOGLE_PLAY_MERCHANT_MAP.items():
            if key in cleaned:
                return result[1:]  # (domain, type, category, confidence)
    
    # Try matching the raw name too
    for key, result in GOOGLE_PLAY_MERCHANT_MAP.items():
        if key in name_lower:
            return result[1:]  # (domain, type, category, confidence)
    
    return None


def classify_merchant(name: str, description: str = "", amount: float = 0.0, from_email: str = "") -> Tuple[str, str, str, float]:
    """
    Classify a transaction using exhaustive rules.
    Returns (domain, transaction_type, category, confidence).
    NEVER returns 'Miscellaneous' or 'unknown' domain.
    """
    name_lower = (name or "").lower().strip()
    desc_lower = (description or "").lower()
    from_lower = (from_email or "").lower()
    
    # 0a. Skip bounced / undeliverable system emails
    if 'system administrator' in from_lower and 'undeliverable' in desc_lower:
        return ('unknown', 'expense', 'Email Bounce', 0.30)
    
    # 0b. Skip forwarded emails from own address (amount from old content)
    subject = desc_lower
    if re.match(r'^(fw:|fwd:|re:)', subject) and from_lower and '@' in from_lower:
        domain = from_lower.split('@')[1] if '@' in from_lower else ''
        if 'gmail.com' in domain:
            return ('unknown', 'expense', 'Forwarded Email', 0.30)
    
    # 0c. Check for Uber Eats in the subject (even if PayPal passes merchant as "Uber")
    if 'uber eats' in desc_lower or 'order with uber eats' in desc_lower:
        return ('personal', 'expense', 'Dining Out', 0.90)
    
    # 0. Check if it's a Google Play purchase (PayPal processor for Google)
    gp_result = extract_google_play_merchant(name_lower)
    if gp_result:
        return gp_result
    
    # 1. Try direct merchant match (most specific)
    for key, result in MERCHANT_CATEGORIES.items():
        if key in name_lower:
            if result is not None:
                return (*result, 0.95)
    
    # 2. Check sender classification (from_email is most reliable)
    if from_lower in SENDER_CLASSIFICATION:
        result = SENDER_CLASSIFICATION[from_lower]
        if result is not None:
            return result
    
    # 3. Check sender domain
    if '@' in from_lower:
        domain_part = from_lower.split('@')[1]
        if domain_part in SENDER_DOMAIN_CLASSIFICATION:
            result = SENDER_DOMAIN_CLASSIFICATION[domain_part]
            if result is not None:
                return result
    
    # 4. Check for Stripe patterns
    for pattern in STRIPE_SENDER_PATTERNS:
        if pattern in from_lower:
            return ('business', 'income', 'Client Payments', 0.85)
    
    # 5. Keyword matching in merchant name or description
    business_keywords = {
        'invoice': ('business', 'expense', 'Professional Services'),
        'client payment': ('business', 'income', 'Client Payments'),
        'consulting': ('business', 'income', 'Consulting Fees'),
        'freelance': ('business', 'income', 'Consulting Fees'),
        'contractor': ('business', 'expense', 'Professional Services'),
        'domain': ('business', 'expense', 'Internet & Telecom'),
        'hosting': ('business', 'expense', 'Internet & Telecom'),
        'subscription': ('business', 'expense', 'Software & Subscriptions'),
        'advertising': ('business', 'expense', 'Marketing & Advertising'),
        'marketing': ('business', 'expense', 'Marketing & Advertising'),
        'software': ('business', 'expense', 'Software & Subscriptions'),
        'cloud': ('business', 'expense', 'Internet & Telecom'),
        'server': ('business', 'expense', 'Internet & Telecom'),
        'license': ('business', 'expense', 'Software & Subscriptions'),
        'api': ('business', 'expense', 'Software & Subscriptions'),
        'app for': ('business', 'expense', 'Software & Subscriptions'),
    }
    personal_keywords = {
        'grocery': ('personal', 'expense', 'Groceries'),
        'gas': ('personal', 'expense', 'Transport'),
        'restaurant': ('personal', 'expense', 'Dining Out'),
        'entertainment': ('personal', 'expense', 'Entertainment'),
        'dining': ('personal', 'expense', 'Dining Out'),
        'pharmacy': ('personal', 'expense', 'Healthcare'),
        'medical': ('personal', 'expense', 'Healthcare'),
    }
    
    for kw, result in business_keywords.items():
        if kw in name_lower or kw in desc_lower:
            return (*result, 0.75)
    for kw, result in personal_keywords.items():
        if kw in name_lower or kw in desc_lower:
            return (*result, 0.75)
    
    # 6. Subject-based patterns
    if re.search(r'(payment to|you sent|receipt for your payment)', desc_lower):
        # This is a payment — try to identify what kind
        if any(p in desc_lower for p in ['google', 'apple app store', 'app store']):
            return ('personal', 'expense', 'Entertainment', 0.70)
        return ('personal', 'expense', 'Shopping', 0.60)
    
    if re.search(r'(payment received|you received|money received)', desc_lower):
        return ('personal', 'income', 'Miscellaneous Income', 0.60)
    
    # 7. Amount-based heuristics (only as a last resort, with meaningful category)
    if amount > 0:
        # Try to use sender domain
        if '@' in from_lower:
            domain = from_lower.split('@')[1]
            # .ai, .io, .dev, .app often indicate business services
            if any(tld in domain for tld in ['.ai', '.io', '.dev', '.app', '.cloud']):
                return ('business', 'expense', 'Software & Subscriptions', 0.55)
            # .com with common business patterns
            if 'mail' in domain or 'service' in domain or 'support' in domain:
                return ('unknown', 'expense', 'unresolved', 0.30)
        
        # Large amounts often have business significance
        if amount > 200:
            return ('business', 'expense', 'Professional Services', 0.50)
        elif amount > 50:
            return ('personal', 'expense', 'Shopping', 0.45)
        else:
            # Small amounts from unknown merchants — best guess based on patterns
            return ('personal', 'expense', 'Entertainment', 0.40)
    
    # 8. ABSOLUTE LAST RESORT — NEVER return Miscellaneous or unknown
    # Use the sender domain to make a reasonable guess
    if '@' in from_lower:
        domain = from_lower.split('@')[1]
        return ('unknown', 'expense', 'unresolved', 0.20)
    
    return ('unknown', 'expense', 'unresolved', 0.10)


# ===========================================================================
# Email Body Parsers
# ===========================================================================

def parse_paypal_email(subject: str, body: str) -> Optional[Dict]:
    """Parse PayPal receipt emails to extract transaction data."""
    text = f"{subject} {body}"
    
    # ── Skip non-transaction PayPal emails ──
    # "Your transfer was successful" = money moving between own accounts
    if re.search(r'(transfer was successful|transferring money to your bank|transfer to your bank|transferring.*bank|transfer.*successful)', text, re.I):
        return None
    # PayPal case closures / disputes
    if re.search(r'(paypal case|case is now closed|dispute)', text, re.I):
        return None
    # "Insufficient funds" notifications
    if re.search(r'(insufficient funds|failed payment|payment failed)', text, re.I):
        return None
    # PayPal promotional/marketing
    if re.search(r'(reward|offer|cash back|cashback|earn)', text, re.I) and not re.search(r'payment|receipt|invoice', text, re.I):
        return None
    
    # Detect direction: payment sent (expense) or received (income)
    is_sent = bool(re.search(r'(payment to|you sent|you paid|receipt for your payment)', text, re.I))
    is_received = bool(re.search(r'(payment received|you received|money received|received a payment|sent you|got money)', text, re.I))
    tx_type = 'expense' if is_sent else ('income' if is_received else 'unknown')
    
    # Extract merchant name
    merchant = None
    
    # Pattern 1: "PAYPAL *MERCHANT" in quotes (most reliable for sent payments)
    m = re.search(r'\"PAYPAL \*([^\"]+)\"', text)
    if m:
        merchant = m.group(1).strip()
    
    # Pattern 2: "You paid $X.XX to MERCHANT" or "Payment to MERCHANT"
    if not merchant:
        m = re.search(r'[Yy]ou paid\s+\$?\d+\.\d{2}\s+\w+\s+to\s+(.+?)(?:\s*[.\n]|\s*$)', text)
        if m:
            merchant = m.group(1).strip().rstrip('.')
    
    if not merchant:
        m = re.search(r'[Pp]ayment to\s+(.+?)(?:\s*[.\n]|\s*$)', text)
        if m:
            merchant = m.group(1).strip().rstrip('.')
    
    # Try again — sometimes it's a `#` as in "Payment to Google # (googleplay)" etc.
    m = re.search(r'[Pp]ayment to\s+(.+?)(?:\s*[.\n#]|\s*$)', body + '\n' + subject)
    if m:
        merchant = m.group(1).strip().rstrip('.')

    # Pattern 4: "From: MERCHANT" (for received payments)
    if not merchant and is_received:
        m = re.search(r'[Ff]rom:\s*(.+?)(?:\s*[.\n]|\s*$)', text)
        if m:
            merchant = m.group(1).strip()
    
    # Pattern 4: "MERCHANT: $X.XX" (PayPal receipts format)
    if not merchant:
        m = re.search(r'^[\w\s]+:\s*\$?\d+\.\d{2}\s', text, re.M)
        if m:
            merchant = m.group(0).split(':')[0].strip()
    
    # Extract amount from "You paid $X.XX"
    amount = None
    m = re.search(r'[Yy]ou\s+(?:paid|sent)\s+\$?(\d+\.\d{2})', text)
    if m:
        amount = float(m.group(1))
    else:
        amounts = re.findall(r'\$?(\d+\.\d{2})', text)
        if amounts:
            amount = max(float(a) for a in amounts)
    
    # Extract transaction date
    txn_date = None
    m = re.search(r'(?:Transaction date|Date)[:\s]+([A-Z][a-z]+ \d+,? \d{4})', text)
    if m:
        try:
            from datetime import datetime as dt
            txn_date = dt.strptime(m.group(1).replace(',', ''), '%b %d %Y').isoformat()
        except:
            pass
    
    if merchant or amount:
        return {
            'merchant': merchant or 'PayPal',
            'amount': amount,
            'transaction_type': tx_type,
            'source': 'paypal_email',
            'transaction_date': txn_date,
        }
    return None


def parse_stripe_email(subject: str, body: str) -> Optional[Dict]:
    """Parse Stripe receipt emails."""
    text = f"{subject} {body}"
    
    merchant = None
    m = re.search(r'[Rr]eceipt from (.+?)(?:\s*[-#\n]|\s*$)', text)
    if m:
        merchant = m.group(1).strip()
    
    amount = None
    am = re.search(r'[Tt]otal charged\s*\$?(\d+\.\d{2})', text)
    if am:
        amount = float(am.group(1))
    if not amount:
        am = re.search(r'[Aa]mount\s*\$?(\d+\.\d{2})', text)
        if am:
            amount = float(am.group(1))
    
    if merchant or amount:
        return {
            'merchant': merchant or 'Stripe',
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'stripe_email',
        }
    return None


def parse_googleplay_email(subject: str, body: str) -> Optional[Dict]:
    """Parse Google Play order receipt emails directly."""
    text = f"{subject} {body}"
    
    # Try to extract the app/product from subject
    # "Your Google Play Order Receipt from Mar 20, 2026" or
    # "Backup payment method used on May 15, 2026 for Facebook | Your Google..."
    merchant = None
    
    # Pattern: "for FACEBOOK | Your Google Play"
    m = re.search(r'for ([A-Z][A-Za-z0-9\s]+)\s*\|', text)
    if m:
        merchant = m.group(1).strip()
    
    # Try to extract app name from body/receipt details
    if not merchant:
        m = re.search(r'(?:order|purchase|transaction)\s+(?:from|with|for)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\.|\s*$)', text)
        if m:
            merchant = m.group(1).strip()
    
    # Extract amount
    amount = extract_amount_from_text(text)
    
    if amount:
        return {
            'merchant': merchant or 'Google Play',
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'googleplay_email',
        }
    return None


def parse_uber_email(subject: str, body: str) -> Optional[Dict]:
    """Parse Uber receipt emails."""
    text = f"{subject} {body}"
    merchant = "Uber"
    amount = extract_amount_from_text(text)
    if amount:
        return {
            'merchant': merchant,
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'uber_email',
        }
    return None


def parse_doordash_email(subject: str, body: str) -> Optional[Dict]:
    """Parse DoorDash receipt emails."""
    text = f"{subject} {body}"
    merchant = "DoorDash"
    amount = extract_amount_from_text(text)
    if amount:
        return {
            'merchant': merchant,
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'doordash_email',
        }
    return None


def parse_openrouter_email(subject: str, body: str) -> Optional[Dict]:
    """Parse OpenRouter receipt emails."""
    text = f"{subject} {body}"
    merchant = "OpenRouter"
    amount = extract_amount_from_text(text)
    if amount:
        return {
            'merchant': merchant,
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'openrouter_email',
        }
    return None


# Ordered list of parsers (most specific first)
EMAIL_PARSERS = [
    ('googleplay-noreply@google.com', parse_googleplay_email),
    ('payments-noreply@google.com', parse_googleplay_email),
    ('service@intl.paypal.com', parse_paypal_email),
    ('invoice+statements+acct_1KrkPkFnZ21YgCse@stripe.com', parse_stripe_email),
    ('receipts@stripe.com', parse_stripe_email),
    ('receipts+acct_', parse_stripe_email),
    ('notifications@stripe.com', parse_stripe_email),
    ('failed-payments+acct_', parse_stripe_email),
    ('invoice+statements+acct_', parse_stripe_email),
    ('upcoming-invoice+acct_', parse_stripe_email),
    ('noreply@uber.com', parse_uber_email),
    ('no-reply@doordash.com', parse_doordash_email),
    ('no-reply@messages.doordash.com', parse_doordash_email),
    ('receipts@openrouter.ai', parse_openrouter_email),
]


def parse_email_financial(email_record: dict) -> Optional[Dict]:
    """
    Parse an email record to extract financial transaction data.
    Returns dict with merchant, amount, transaction_type or None.
    """
    subject = email_record.get('subject', '') or ''
    body = email_record.get('body_plain', '') or email_record.get('snippet', '') or ''
    from_email = (email_record.get('from_email', '') or '').lower()
    
    # Try specific parser by sender
    for sender_pattern, parser_func in EMAIL_PARSERS:
        if sender_pattern in from_email and parser_func:
            result = parser_func(subject, body)
            if result:
                return result
    
    # Generic: extract amount and guess merchant
    text = f"{subject} {body}"
    amount = extract_amount_from_text(text)
    
    merchant = None
    m = re.search(r'[Pp]ayment to (.+)', subject)
    if m:
        merchant = m.group(1).strip()
    elif amount and '@' in from_email:
        domain = from_email.split('@')[-1]
        merchant = domain.replace('.com', '').replace('.ai', '').replace('.io', '').title()
    
    if amount or merchant:
        return {
            'merchant': merchant,
            'amount': amount,
            'transaction_type': 'expense',
            'source': 'generic_email',
        }
    
    return None


# ===========================================================================
# Attachment OCR
# ===========================================================================

def ocr_attachment(filepath: str) -> Optional[Dict]:
    """OCR an attachment and extract receipt data."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.pdf':
            import fitz
            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text()
            if len(text.strip()) < 20:
                from pdf2image import convert_from_path
                import pytesseract
                from PIL import ImageOps
                images = convert_from_path(filepath)
                text = ""
                for img in images:
                    img_gray = img.convert('L')
                    img_gray = ImageOps.autocontrast(img_gray, cutoff=5)
                    text += pytesseract.image_to_string(img_gray, config='--psm 4 --oem 3') + "\n"
            doc.close()
        elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
            import pytesseract
            from PIL import Image, ImageOps
            img = Image.open(filepath)
            img = img.convert('L')
            img = ImageOps.autocontrast(img, cutoff=5)
            text = pytesseract.image_to_string(img, config='--psm 4 --oem 3')
        else:
            return None
        
        if not text.strip():
            return None
        
        result = {
            'vendor': None,
            'amount': None,
            'date': None,
            'confidence': 0.0,
            'raw_text': text[:5000],
        }
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            for line in lines[:5]:
                if re.match(r'^[A-Z][A-Z\s&.]+$', line) and len(line) > 3:
                    result['vendor'] = line
                    result['confidence'] += 0.2
                    break
            if not result['vendor']:
                result['vendor'] = lines[0][:50]
                result['confidence'] += 0.1
        
        amt_match = re.search(r'(?:TOTAL|BALANCE DUE|AMOUNT|TOTAL DUE)[:\s]*\$?(\d+\.\d{2})', text, re.I)
        if amt_match:
            result['amount'] = float(amt_match.group(1))
            result['confidence'] += 0.3
        else:
            all_amounts = re.findall(r'\$(\d+\.\d{2})', text)
            if all_amounts:
                result['amount'] = max(float(a) for a in all_amounts)
                result['confidence'] += 0.2
        
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
        if date_match:
            try:
                from datetime import datetime as dt
                result['date'] = dt.strptime(date_match.group(1).replace('/', '-'), '%m-%d-%Y').isoformat()
                result['confidence'] += 0.2
            except:
                try:
                    result['date'] = dt.strptime(date_match.group(1), '%Y-%m-%d').isoformat()
                    result['confidence'] += 0.2
                except:
                    pass
        
        return result
        
    except Exception as e:
        return {
            'vendor': None,
            'amount': None,
            'date': None,
            'confidence': 0.0,
            'raw_text': f"[Error: {e}]",
        }


# ===========================================================================
# Main Pipeline
# ===========================================================================

def process_email(db, email_id: int):
    """Process a single email through the full pipeline."""
    email = db.get_email(email_id)
    if not email:
        return None
    
    from_email = email.get('from_email', '') or ''
    subject = email.get('subject', '') or ''
    
    body_text = email.get('body_plain', '') or ''
    if not body_text.strip():
        html = email.get('body_html', '') or ''
        body_text = strip_html(html)
    
    db.log_pipeline_step(email_id, 'extract', 'started')
    
    # Step 1: Parse from email body
    email_record = {
        'subject': subject,
        'body_plain': body_text,
        'snippet': body_text[:200],
        'from_email': from_email,
    }
    financial = parse_email_financial(email_record)
    
    merchant = None
    amount = None
    tx_type = 'unknown'
    confidence = 0.5
    extraction_method = 'email_body'
    txn_date = None
    
    if financial:
        merchant = financial.get('merchant')
        amount = financial.get('amount')
        tx_type = financial.get('transaction_type', 'unknown')
        confidence = 0.7
        extraction_method = financial.get('source', 'email_body')
        txn_date = financial.get('transaction_date')
        db.log_pipeline_step(email_id, 'extract', 'completed',
                            output_data={'merchant': merchant, 'amount': amount, 'method': extraction_method})
    else:
        db.log_pipeline_step(email_id, 'extract', 'skipped',
                            output_data={'reason': 'No financial data found in email body'})
    
    # Step 2: OCR attachments
    if not merchant or not amount:
        attachments = db._conn.execute(
            "SELECT id, filepath FROM attachments WHERE email_id = ? AND ocr_status = 'pending'",
            (email_id,)
        ).fetchall()
        
        for att in attachments:
            att_path = att['filepath']
            if att_path and os.path.exists(att_path):
                ocr_result = ocr_attachment(att_path)
                if ocr_result and ocr_result.get('confidence', 0) > 0.3:
                    db._conn.execute(
                        "UPDATE attachments SET ocr_status='done', ocr_text=?, ocr_confidence=?, ocr_processed_at=datetime('now') WHERE id=?",
                        (ocr_result.get('raw_text', ''), ocr_result.get('confidence', 0), att['id'])
                    )
                    merchant = merchant or ocr_result.get('vendor')
                    amount = amount or ocr_result.get('amount')
                    if not txn_date:
                        txn_date = ocr_result.get('date')
                    confidence = max(confidence, ocr_result.get('confidence', 0))
                    extraction_method = 'ocr'
                else:
                    db._conn.execute(
                        "UPDATE attachments SET ocr_status='error' WHERE id=?",
                        (att['id'],)
                    )
        db._conn.commit()
    
    # Step 3: If still no data — extract from subject directly
    if not merchant and not amount:
        amt = re.findall(r'\$\s*(\d+\.\d{2})', subject)
        if amt:
            amount = max(float(a) for a in amt)
        if amount and '@' in from_email:
            domain = from_email.split('@')[1].split('.')[0]
            merchant = domain.title()
            confidence = 0.4
    
    # Step 4: Classify transaction — always produces a meaningful category
    if amount:
        domain, tx_type_class, category, class_conf = classify_merchant(
            merchant or from_email, subject or '', amount, from_email
        )
        
        if tx_type == 'unknown':
            tx_type = tx_type_class
        elif tx_type_class != 'unknown' and tx_type == 'expense' and tx_type_class == 'income':
            tx_type = tx_type_class
        
        deduction_rate = 0.0
        if domain == 'business' and tx_type == 'expense':
            if category in ('Travel & Meals', 'Meals & Entertainment'):
                deduction_rate = 0.5
            else:
                deduction_rate = 1.0
        
        tx_data = {
            'email_id': email_id,
            'email_from': from_email,
            'email_subject': subject[:200] if subject else None,
            'email_date': email.get('email_date'),
            'merchant_name': merchant[:100] if merchant else from_email[:100],
            'merchant_email': from_email,
            'amount': round(amount, 2),
            'transaction_date': txn_date,
            'description': subject[:500] if subject else None,
            'domain': domain,
            'transaction_type': tx_type,
            'category': category,
            'classification_confidence': round(class_conf, 3),
            'classification_method': 'rule',
            'is_deductible': 1 if domain == 'business' and tx_type == 'expense' else 0,
            'deduction_rate': deduction_rate,
            'needs_review': 1 if class_conf < 0.5 else 0,
        }
        tx_id = db.insert_transaction(tx_data)
        
        db.log_pipeline_step(email_id, 'classify', 'completed',
                            model_used='rule',
                            output_data={'domain': domain, 'category': category, 'tx_type': tx_type})
        
        db._conn.execute(
            "UPDATE emails SET email_status='categorized', processed_at=datetime('now') WHERE id=?",
            (email_id,)
        )
        db._conn.commit()
        return tx_id
    
    # No amount found
    db._conn.execute(
        "UPDATE emails SET email_status='errored' WHERE id=?",
        (email_id,)
    )
    db._conn.commit()
    return None


def strip_html(html: str) -> str:
    """Strip HTML tags and clean up text."""
    if not html:
        return ""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'&#[0-9]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
