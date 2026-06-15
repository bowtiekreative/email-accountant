---
name: receipt-ocr-extraction
description: "Extract structured data from receipt and invoice images/PDFs using OCR. Parse vendor names, dates, amounts, line items. Handle multiple formats and low-quality scans."
domain: financial
tags:
  - ocr
  - receipt-parsing
  - image-extraction
  - pdf
  - pytesseract
  - data-extraction
---

# Receipt OCR & Extraction

## Overview

Extract structured financial data from receipt images, PDFs, and emailed invoices. Combines PyMuPDF (PDF parsing) + Tesseract OCR (image fallback) + regex patterns for merchant/amount/date extraction. Handles everything from crisp emailed PDFs to crumpled photo receipts.

## Pipeline

```
Email with attachment ─┬─ PDF ──► PyMuPDF (text extraction)
                       │               │
                       └─ Image ─► Tesseract OCR
                                     │
                                     ▼
                          Text + Patterns
                                     │
                          Vendor, Date, Amount
                                     │
                              Confidence Score
```

## Setup

```bash
pip install pytesseract pdf2image pillow
# System tesseract (Ubuntu/Debian):
apt-get install -y tesseract-ocr
```

## Core Functions

### PDF Text Extraction
```python
import fitz  # PyMuPDF

def extract_pdf_text(filepath):
    """Extract text from PDF using PyMuPDF (fast, no OCR needed for text PDFs)."""
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    return text.strip()
```

### OCR (Image Fallback)
```python
import pytesseract
from PIL import Image

def ocr_image(filepath):
    """OCR a receipt image with Tesseract. Falls back from PDF text if needed."""
    img = Image.open(filepath)
    # Preprocess: convert to grayscale, increase contrast
    img = img.convert('L')
    # Apply threshold for better OCR on faded receipts
    from PIL import ImageOps
    img = ImageOps.autocontrast(img, cutoff=5)
    
    config = '--psm 4 --oem 3'  # PSM 4 = assume single column of text
    text = pytesseract.image_to_string(img, config=config)
    return text.strip()
```

### Smart Extraction Router
```python
import os

def extract_receipt_text(filepath):
    """Route to PDF or OCR based on file type."""
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.pdf':
        text = extract_pdf_text(filepath)
        # If PDF is scanned image (no text layer), fall back to OCR
        if len(text.strip()) < 20:  # Empty or scanned PDF
            from pdf2image import convert_from_path
            images = convert_from_path(filepath)
            text = ""
            for img in images:
                text += ocr_image(img) + "\n"
        return text
    
    elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
        return ocr_image(filepath)
    
    return ""
```

## Field Extraction with Regex

### Vendor Extraction
```python
VENDOR_PATTERNS = [
    # Common header patterns
    (r'^(.*?)(?:\n|$)', 0),           # First line of receipt
    (r'THANK YOU[.\s]*(.*?)[.\s]*$', 1),  # After "thank you"
    (r'(?:^|\n)\s*([A-Z][A-Z\s&.]+)\s*\n', 1),  # ALL CAPS line
    (r'(?:Welcome to|Store|Location|Branch)\s*[:#]?\s*(.+?)$', 1),
]
```

### Date Extraction
```python
DATE_PATTERNS = [
    (r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', strptime),       # MM/DD/YYYY
    (r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', strptime),          # YYYY-MM-DD
    (r'(Date|Dated?)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', 2),
    (r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', None),        # ISO format
]
```

### Amount Extraction
```python
AMOUNT_PATTERNS = [
    (r'(?:TOTAL|BALANCE\s+DUE|AMOUNT)[:\s]*\$?(\d+\.\d{2})', 1),
    (r'(?:SUBTOTAL|TAX)[:\s]*\$?(\d+\.\d{2})', 1),
    (r'\$(\d+\.\d{2})\s*$', 1),                            # $XX.XX at EOL
    (r'(?:CREDIT|DEBIT|CHARGED?)[:\s]*\$?(\d+\.\d{2})', 1),
]
```

### Full Extraction Function
```python
import re
from datetime import datetime

def extract_receipt_data(filepath):
    """Extract structured data from a receipt image or PDF."""
    text = extract_receipt_text(filepath)
    
    data = {
        'vendor': None,
        'date': None,
        'amount': None,
        'items': [],
        'subtotal': None,
        'tax': None,
        'confidence': 0.0,
        'raw_text': text,
        'filepath': filepath,
    }
    
    # Vendor
    for pattern, group in VENDOR_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            data['vendor'] = match.group(group).strip()
            data['confidence'] += 0.2
            break
    
    # Date
    for pattern, _ in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(min(2, match.lastindex or 1))
            try:
                data['date'] = datetime.strptime(date_str.replace('/', '-'), '%m-%d-%Y')
                data['confidence'] += 0.2
            except:
                try:
                    data['date'] = datetime.strptime(date_str, '%Y-%m-%d')
                    data['confidence'] += 0.2
                except:
                    pass
            break
    
    # Amount
    for pattern, group in AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                data['amount'] = float(match.group(group))
                data['confidence'] += 0.3
                break
            except:
                pass
    
    # Line items (items between headers and total)
    data['items'] = extract_line_items(text)
    
    return data


def extract_line_items(text):
    """Extract individual line items from receipt text."""
    items = []
    lines = text.split('\n')
    in_items = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Match lines like "Item Name          $12.99" or "SKU123 Widget 12.99"
        match = re.match(r'^(.+?)\s+\$?(\d+\.?\d*)\s*$', line)
        if match:
            items.append({
                'description': match.group(1).strip(),
                'price': float(match.group(2))
            })
    
    return items
```

## Known Merchant Receipt Formats

| Merchant | Pattern | Fields to Extract |
|---|---|---|
| Amazon | "Order #" + items + "Subtotal" + "Total" | Order ID, items, shipping, total |
| Starbucks | "Store #" + "Items" + "Total" | Location, items, total |
| Uber/UberEats | "Trip fare" or "Order from X" | Route/vendor, fare, tip |
| Square | "Merchant:" + items + "Total" | Merchant name, items, total |
| PayPal | "Transaction ID:" + "Amount" + "Fee" | Transaction ID, gross, fee, net |
| Stripe | "Receipt from" + items + "Total charged" | Merchant, description, amount |

## Confidence Scoring

| Score | Meaning | Action |
|---|---|---|
| 0.0 - 0.3 | Poor — couldn't parse key fields | Flag for manual review |
| 0.3 - 0.6 | Partial — has some fields | Suggest category, human confirms |
| 0.6 - 0.8 | Good — most fields extracted correctly | Auto-process with peer review |
| 0.8 - 1.0 | Excellent — all fields confident | Auto-categorize, no review needed |

## GOTCHAs

- Scanned PDFs have NO text layer — PyMuPDF returns empty; always check text length and fall back to OCR
- Faded thermal receipt paper: boost contrast and threshold before OCR
- International receipts: date format varies (DD/MM vs MM/DD) — check locale or context clues
- Split payments: "TOTAL" might be partial if there's a tip or discount line below
- Multiple currencies: detect `$`, `€`, `£`, `¥` in text; default to user's home currency if ambiguous
- Tables without borders: Tesseract may merge columns — use PSM 4 or hand-tune
- Watermark / background text on invoice PDFs can confuse OCR — filter out repeated text