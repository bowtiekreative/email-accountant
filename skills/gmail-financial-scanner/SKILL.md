---
name: gmail-financial-scanner
description: "Scan Gmail inbox for financial emails — receipts, invoices, payment confirmations, and income notifications. Handles pagination, historical backfill, attachment download, and incremental updates."
domain: financial
tags:
  - gmail
  - email-scanning
  - financial-data
  - receipts
  - invoices
  - payments
---

# Gmail Financial Scanner

## Overview

The **Gmail Financial Scanner** connects to your Gmail inbox via the Gmail API, searches for financial-related emails using targeted queries, extracts attachments, and prepares raw data for the classification pipeline. It supports scanning ALL historical emails (years back) and incremental daily updates.

## Prerequisites

- Google Cloud Project with **Gmail API** enabled
- OAuth 2.0 credentials (`credentials.json`) with scope `https://www.googleapis.com/auth/gmail.readonly`
- Python 3.8+ with `google-api-python-client`, `google-auth-oauthlib`

## Setup

### 1. Enable Gmail API
```bash
# In Google Cloud Console:
# 1. Create or select a project
# 2. Enable Gmail API
# 3. Create OAuth 2.0 credentials (Desktop app type)
# 4. Download as credentials.json
```

### 2. Authenticate
```python
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle, os

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)
```

## Search Queries

### Receipts & Purchases
| Merchant Pattern | Gmail Query |
|---|---|
| Amazon | `from:order-update@amazon.com OR from:shipment-tracking@amazon.com` |
| Stripe | `from:stripe.com subject:"receipt"` |
| PayPal | `from:service@paypal.com subject:receipt OR subject:payment received` |
| Shopify | `from:shopify.com subject:receipt OR subject:invoice` |
| Square | `from:squareup.com subject:receipt` |
| Etsy | `from:etsy.com subject:you bought` |
| Generic | `subject:receipt OR subject:invoice OR subject:order confirmation` |

### Income & Payments Received
| Source Pattern | Gmail Query |
|---|---|
| PayPal received | `from:service@paypal.com subject:"you received a payment"` |
| Stripe payouts | `from:stripe.com subject:payout` |
| Direct deposit | `from:payroll@ OR subject:"direct deposit"` |
| Wire transfer | `subject:wire transfer OR subject:payment received` |
| Freelance platforms | `from:upwork.com OR from:fiverr.com OR from:freelancer.com` |

### Failed Payments
```gmail
subject:"payment failed" OR subject:"transaction declined" OR subject:"payment declined"
OR subject:"insufficient funds" OR from:"billing@*" subject:"failed"
```

## Implementation

### Core Scanner

```python
def search_financial_emails(service, query, year=None, max_results=500):
    """
    Search Gmail for financial emails matching query.
    Handles pagination automatically.
    """
    all_messages = []
    page_token = None
    
    # Add year filter if specified
    if year:
        query = f"{query} after:{year}/1/1 before:{year+1}/1/1"
    
    while True:
        request = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results,
            pageToken=page_token
        )
        response = request.execute()
        
        messages = response.get('messages', [])
        all_messages.extend(messages)
        
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    
    return all_messages


def get_email_details(service, msg_id):
    """Get full email details including body and headers."""
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()
    
    headers = {}
    for header in msg['payload']['headers']:
        name = header['name'].lower()
        headers[name] = header['value']
    
    return {
        'id': msg_id,
        'date': headers.get('date', ''),
        'from': headers.get('from', ''),
        'subject': headers.get('subject', ''),
        'to': headers.get('to', ''),
        'snippet': msg.get('snippet', ''),
        'label_ids': msg.get('labelIds', []),
    }
```

### Attachment Download

```python
def get_attachments(service, msg_id, download_dir='downloads'):
    """Download all attachments from an email."""
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()
    
    attachments = []
    
    def process_parts(parts):
        for part in parts:
            if part.get('filename') and part.get('body', {}).get('attachmentId'):
                filename = part['filename']
                att_id = part['body']['attachmentId']
                
                # Get attachment data
                att = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=att_id
                ).execute()
                
                data = base64.urlsafe_b64decode(att['data'])
                
                # Save locally
                filepath = os.path.join(download_dir, filename)
                os.makedirs(download_dir, exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(data)
                
                attachments.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': len(data),
                    'mime_type': part.get('mimeType', '')
                })
            
            if part.get('parts'):
                attachments.extend(process_parts(part['parts']))
        
        return attachments
    
    return process_parts(msg['payload'].get('parts', []))
```

### Historical Backfill (Years)

```python
def scan_all_years(service, start_year=2010, end_year=2026):
    """Scan every year from start_year to end_year."""
    all_results = {}
    
    for year in range(start_year, end_year + 1):
        print(f"Scanning {year}...")
        
        queries = {
            'receipts': 'subject:receipt OR subject:order confirmation',
            'invoices': 'subject:invoice OR subject:bill',
            'payments_received': 'subject:"payment received" OR subject:"you received"',
            'failed_payments': 'subject:"payment failed" OR subject:"declined"',
        }
        
        year_data = {}
        for category, query in queries.items():
            messages = search_financial_emails(service, query, year=year)
            year_data[category] = []
            
            for msg in messages[:50]:  # Limit per query to avoid rate limits
                details = get_email_details(service, msg['id'])
                attachments = get_attachments(service, msg['id'])
                year_data[category].append({
                    **details,
                    'attachments': attachments
                })
        
        all_results[year] = year_data
    
    return all_results
```

### Incremental / Daily Scan

```python
def scan_recent(service, days_back=3):
    """Scan recent emails for incremental updates."""
    import time
    after_date = int(time.time()) - (days_back * 86400)
    
    query = f"(subject:receipt OR subject:invoice OR subject:payment OR subject:order) after:{after_date}"
    return search_financial_emails(service, query)
```

## Rate Limiting & Best Practices

| Constraint | Strategy |
|---|---|
| Gmail API: 250 queries / user / second | Add 1s delay between batch requests |
| Gmail API: 1M queries / day | Use incremental scanning, avoid re-scanning old emails |
| Large inbox (100k+ emails) | Scan by year, one year per run |
| Attachment size limits | Download during off-peak hours |
| Token expiry | Use refresh token, auto-refresh before scan |

## Know-Your-Merchant Patterns

Store known merchant email patterns to auto-classify:

```python
MERCHANT_PATTERNS = {
    'amazon': ['@amazon.com', 'order-update@', 'shipment-tracking@'],
    'paypal': ['@paypal.com', 'service@paypal'],
    'stripe': ['@stripe.com', 'receipts@stripe'],
    'shopify': ['@shopify.com', 'orders@shopify'],
    'square': ['@squareup.com', 'receipt@square'],
    'etsy': ['@etsy.com', 'noreply@etsy'],
    'uber': ['@uber.com', 'uberreceipts@'],
    'doordash': ['@doordash.com'],
    'netflix': ['@netflix.com', 'info@netflix'],
    'spotify': ['@spotify.com'],
    'google': ['payments-noreply@google.com', 'googleplay@'],
}
```

## Verification

Run a test scan of the current year to verify:
```python
from gmail_scanner import get_gmail_service, scan_all_years

service = get_gmail_service()
result = scan_all_years(service, start_year=2025, end_year=2025)
print(f"Found {sum(len(v) for k,v in result[2025].items())} financial emails in 2025")
```

## GOTCHAs

- Gmail API quota resets daily at midnight PST — plan large backfills around this
- Emails in Spam are NOT returned by default — use `includeSpamTrash=True` if needed
- PDF attachments may be scanned as images — OCR pipeline handles this
- Rate limit errors return HTTP 429 — implement exponential backoff (wait 1s, 2s, 4s...)
- Gmail search syntax: `after:2024/1/1 before:2024/2/1` — use YYYY/M/D format
- OAuth consent screen: must publish app if >100 users. Testing with 1 user = no publication needed