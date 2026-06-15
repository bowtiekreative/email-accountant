---
name: tax-preparation-system
description: "Prepare tax-ready financial reports with IRS Schedule C categories, deductible expense tracking, and year-end summaries for filing."
domain: financial
tags:
  - taxes
  - irs-schedule-c
  - tax-preparation
  - deductions
  - year-end
  - filing
---

# Tax Preparation System

## Overview

Prepares tax-ready reports from the year's transactions, organized by IRS Schedule C categories. Tracks deductible vs non-deductible expenses, calculates deduction rates (e.g. 50% for meals), and produces reports suitable for filing or sharing with your accountant.

## IRS Schedule C Mapping

Every business expense transaction is mapped to an IRS Schedule C line item:

```python
IRS_SCHEDULE_C = {
    'Advertising': {
        'line': 8,
        'description': 'Advertising and marketing costs',
        'examples': ['Google Ads', 'Facebook Ads', 'flyers', 'SEO services'],
        'deduction_rate': 1.0,
    },
    'Contract Labor': {
        'line': 11,
        'description': 'Payments to independent contractors',
        'examples': ['freelancers', '1099 workers', 'consultants'],
        'deduction_rate': 1.0,
    },
    'Insurance': {
        'line': 15,
        'description': 'Business insurance premiums',
        'examples': ['liability insurance', 'professional indemnity'],
        'deduction_rate': 1.0,
    },
    'Legal & Professional': {
        'line': 17,
        'description': 'Legal, accounting, and professional fees',
        'examples': ['lawyer', 'accountant', 'bookkeeper'],
        'deduction_rate': 1.0,
    },
    'Office Expense': {
        'line': 18,
        'description': 'Office supplies, postage, software subscriptions',
        'examples': ['paper', 'ink', 'software licenses', 'domain names'],
        'deduction_rate': 1.0,
    },
    'Supplies': {
        'line': 22,
        'description': 'Materials and supplies consumed in business',
        'examples': ['raw materials', 'packaging', 'shipping supplies'],
        'deduction_rate': 1.0,
    },
    'Travel': {
        'line': 24a,
        'description': 'Business travel expenses',
        'examples': ['flights', 'hotels', 'rental cars', 'conference fees'],
        'deduction_rate': 1.0,
    },
    'Meals & Entertainment': {
        'line': 24b,
        'description': 'Business meals with clients',
        'examples': ['client lunch', 'business dinner', 'team meal'],
        'deduction_rate': 0.5,  # 50% deductible under TCJA
    },
    'Utilities': {
        'line': 25,
        'description': 'Internet, phone, electricity for business',
        'examples': ['cell phone', 'internet', 'web hosting'],
        'deduction_rate': 1.0,
    },
    'Home Office': {
        'line': 30,
        'description': 'Home office deduction (simplified or regular method)',
        'examples': ['home office % of rent/mortgage', 'office furniture'],
        'deduction_rate': 1.0,
    },
    'Other Expenses': {
        'line': 27a,
        'description': 'Other business expenses not categorized above',
        'examples': ['bank fees', 'licenses', 'permits', 'miscellaneous'],
        'deduction_rate': 1.0,
    },
}
```

## Tax Report Generator

```python
import sqlite3
from collections import defaultdict

def generate_tax_report(year, base_dir='data'):
    """Generate a complete tax preparation report for a given year."""
    conn = sqlite3.connect(get_db_path(year, base_dir))
    conn.row_factory = sqlite3.Row
    
    report = {
        'year': year,
        'total_business_income': 0.0,
        'total_business_expenses': 0.0,
        'net_profit': 0.0,
        'deductions_by_line': {},
        'total_deductible': 0.0,
        'non_deductible_expenses': 0.0,
        'personal_expenses': 0.0,
        'flagged_items': [],
        'receipts_missing': 0,
    }
    
    # Business income total
    income_row = conn.execute('''
        SELECT SUM(amount) as total
        FROM transactions
        WHERE domain = 'business' AND type = 'income' AND scan_year = ?
    ''', (year,)).fetchone()
    report['total_business_income'] = round(income_row['total'] or 0.0, 2)
    
    # Expenses by Schedule C line
    expenses = conn.execute('''
        SELECT tax_category, SUM(amount) as total, COUNT(*) as count,
               SUM(amount * deduction_rate) as deductible_amount
        FROM transactions
        WHERE domain = 'business' AND type = 'expense' AND scan_year = ?
        GROUP BY tax_category
        ORDER BY total DESC
    ''', (year,)).fetchall()
    
    deductions = {}
    for row in expenses:
        irs_info = IRS_SCHEDULE_C.get(row['tax_category'], {
            'line': 99,
            'deduction_rate': 1.0,
        })
        deductions[row['tax_category']] = {
            'irs_line': irs_info['line'],
            'total_spent': round(row['total'], 2),
            'count': row['count'],
            'deduction_rate': irs_info['deduction_rate'],
            'deductible_amount': round(row['deductible_amount'] or 0.0, 2),
            'items': get_category_items(conn, year, row['tax_category']),
        }
    
    report['deductions_by_line'] = deductions
    report['total_deductible'] = round(
        sum(d['deductible_amount'] for d in deductions.values()), 2
    )
    report['total_business_expenses'] = round(
        sum(d['total_spent'] for d in deductions.values()), 2
    )
    report['net_profit'] = round(
        report['total_business_income'] - report['total_business_expenses'], 2
    )
    
    # Items needing attention
    report['flagged_items'] = find_flagged_items(conn, year)
    report['receipts_missing'] = count_missing_receipts(conn, year)
    
    # Personal expenses (not tax-relevant but good for overall picture)
    personal = conn.execute('''
        SELECT SUM(amount) as total
        FROM transactions
        WHERE domain = 'personal' AND type = 'expense' AND scan_year = ?
    ''', (year,)).fetchone()
    report['personal_expenses'] = round(personal['total'] or 0.0, 2)
    
    return report


def get_category_items(conn, year, tax_category):
    """Get individual transactions for a specific tax category."""
    items = conn.execute('''
        SELECT email_date, merchant_name, amount, description, 
               deduction_rate, attachment_path
        FROM transactions
        WHERE domain = 'business' AND type = 'expense' 
          AND tax_category = ? AND scan_year = ?
        ORDER BY email_date
    ''', (tax_category, year)).fetchall()
    return [dict(r) for r in items]


def find_flagged_items(conn, year):
    """Find transactions that need attention before filing."""
    flagged = []
    
    # Uncategorized business items
    uncat = conn.execute('''
        SELECT * FROM transactions
        WHERE scan_year = ? AND domain = 'business' AND type = 'expense'
          AND (category IS NULL OR category = 'uncategorized-business')
    ''', (year,)).fetchall()
    for item in uncat:
        flagged.append({
            'merchant': item['merchant_name'],
            'amount': item['amount'],
            'date': item['email_date'],
            'reason': 'Missing tax category'
        })
    
    # High-value single items (audit risk)
    high = conn.execute('''
        SELECT * FROM transactions
        WHERE scan_year = ? AND domain = 'business' AND type = 'expense'
          AND amount > 500
    ''', (year,)).fetchall()
    for item in high:
        flagged.append({
            'merchant': item['merchant_name'],
            'amount': item['amount'],
            'date': item['email_date'],
            'reason': f"High value (${item['amount']:.2f}) — ensure receipt is saved"
        })
    
    return flagged


def count_missing_receipts(conn, year):
    """Count business expenses without attachment/receipt."""
    row = conn.execute('''
        SELECT COUNT(*) as count
        FROM transactions
        WHERE scan_year = ? AND domain = 'business' AND type = 'expense'
          AND (attachment_path IS NULL OR attachment_path = '')
    ''', (year,)).fetchone()
    return row['count']
```

## Form 1040 Schedule C Export

```python
def export_schedule_c(year, output_path, base_dir='data'):
    """Export data structured for IRS Schedule C (Form 1040)."""
    report = generate_tax_report(year, base_dir)
    
    schedule_c = {
        'A': 'Principal business or profession by NAICS code',  # Need user input
        'B': 'Business name (if any)',
        'C': 'Employer ID number (EIN)',
        'line_1': {'label': 'Gross receipts or sales', 'amount': report['total_business_income']},
        'line_2': {'label': 'Returns and allowances', 'amount': 0.0},
        'line_3': {'label': 'Net receipts (line 1 - line 2)', 'amount': report['total_business_income']},
        'line_4': {'label': 'Cost of goods sold (if applicable)', 'amount': 0.0},
        'line_5': {'label': 'Gross profit (line 3 - line 4)', 'amount': report['total_business_income']},
        'line_6': {'label': 'Other income', 'amount': 0.0},
        'line_7': {'label': 'Gross income (line 5 + line 6)', 'amount': report['total_business_income']},
    }
    
    # Map categories to Schedule C lines
    line_mapping = {
        'Advertising': ('line_8', 'Advertising'),
        'Contract Labor': ('line_11', 'Contract labor'),
        'Insurance': ('line_15', 'Insurance (other than health)'),
        'Legal & Professional': ('line_17', 'Legal and professional services'),
        'Office Expense': ('line_18', 'Office expense'),
        'Supplies': ('line_22', 'Supplies'),
        'Travel': ('line_24', 'Travel'),
        'Meals & Entertainment': ('line_24b', 'Deductible meals'),
        'Utilities': ('line_25', 'Utilities'),
        'Home Office': ('line_30', 'Business use of home'),
        'Other Expenses': ('line_27a', 'Other expenses'),
    }
    
    for tax_cat, (line_key, label) in line_mapping.items():
        if tax_cat in report['deductions_by_line']:
            schedule_c[line_key] = {
                'label': label,
                'amount': report['deductions_by_line'][tax_cat]['deductible_amount'],
                'items': report['deductions_by_line'][tax_cat]['items'],
            }
    
    import json
    with open(output_path, 'w') as f:
        json.dump(schedule_c, f, indent=2, default=str)
    
    return output_path
```

## Tax-Ready Report (HTML)

```python
def generate_tax_html(year, output_path=None, base_dir='data'):
    """Generate an HTML tax report ready to share with accountant."""
    report = generate_tax_report(year, base_dir)
    
    if not output_path:
        output_path = f'tax_report_{year}.html'
    
    html = f"""
    <!DOCTYPE html><html><head>
    <meta charset="utf-8"><title>Tax Report {year}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: auto; padding: 20px; background: #0f0f1a; color: #e0e0e0; }}
        h1 {{ color: #00d4aa; }}
        h2 {{ color: #8888ff; border-bottom: 1px solid #333; }}
        .card {{ background: #1a1a2e; padding: 16px; border-radius: 8px; margin: 12px 0; }}
        .income {{ color: #50fa7b; font-weight: bold; }}
        .expense {{ color: #ff5555; }}
        .profit {{ color: #00d4aa; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td, th {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
        .flag {{ background: #2e1a1a; border-left: 3px solid #ff5555; padding: 8px 12px; margin: 4px 0; }}
    </style></head><body>
    <h1>📋 Tax Preparation — {year}</h1>
    
    <div class="summary-grid">
        <div class="card">
            <h3>Business Income</h3>
            <div class="income">${report['total_business_income']:,.2f}</div>
        </div>
        <div class="card">
            <h3>Total Deductible</h3>
            <div class="profit">${report['total_deductible']:,.2f}</div>
        </div>
        <div class="card">
            <h3>Net Profit</h3>
            <div class="expense">${report['net_profit']:,.2f}</div>
        </div>
    </div>
    
    <div class="card">
        <h2>📊 Deductions by Schedule C Line</h2>
        <table>
        <tr><th>IRS Line</th><th>Category</th><th>Spent</th><th>Deductible</th><th>Rate</th><th>Items</th></tr>
    """
    
    for cat, data in sorted(report['deductions_by_line'].items(), key=lambda x: x[1]['irs_line']):
        html += f"""
        <tr>
            <td>Line {data['irs_line']}</td>
            <td>{cat}</td>
            <td>${data['total_spent']:,.2f}</td>
            <td><strong>${data['deductible_amount']:,.2f}</strong></td>
            <td>{int(data['deduction_rate']*100)}%</td>
            <td>{data['count']}</td>
        </tr>"""
    
    html += "</table></div>"
    
    if report['flagged_items']:
        html += '<div class="card"><h2>⚠️ Items Needing Attention</h2>'
        for flag in report['flagged_items']:
            html += f'<div class="flag">{flag["date"]} — {flag["merchant"]}: ${flag["amount"]:.2f}<br><small>{flag["reason"]}</small></div>'
        html += '</div>'
    
    if report['receipts_missing'] > 0:
        html += f'<div class="card"><p>⚠️ {report["receipts_missing"]} business expenses have no receipt attached</p></div>'
    
    html += f"""
    <div class="card">
        <h2>📝 Personal Summary</h2>
        <p>Personal expenses: <span class="expense">${report['personal_expenses']:,.2f}</span></p>
        <p><small>Personal expenses are not tax-deductible and are tracked for overall financial awareness.</small></p>
    </div>
    </body></html>"""
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path
```

## Year-End Checklist

| # | Item | Status |
|---|---|---|
| 1 | Run full yearly scan (ensure ALL emails captured) | ⬜ |
| 2 | Review all uncategorized transactions | ⬜ |
| 3 | Verify merchant→category mappings | ⬜ |
| 4 | Attach receipts for high-value items ($500+) | ⬜ |
| 5 | Categorize meals: 50% deductible, note who & business purpose | ⬜ |
| 6 | Separate personal vs business on mixed accounts | ⬜ |
| 7 | Generate Schedule C export | ⬜ |
| 8 | Verify totals against bank/credit card statements | ⬜ |
| 9 | Export PDF for accountant review | ⬜ |
| 10 | File or save with tax preparation docs | ⬜ |

## GOTCHAs

- Meals deduction rate is 50% (TCJA 2018+). Auto-set this via `deduction_rate = 0.5`
- Hobby loss rule: if business shows a loss 3+ years running, IRS may reclassify it as a hobby. Flag consecutive loss years
- Home office deduction: simplified method ($5/sq ft, max 300 sq ft = $1,500) or regular method (mortgage %). User must choose
- Vehicle expenses: standard mileage rate ($0.655/mi for 2023) vs actual expenses — user needs to choose method
- 1099-NEC threshold: $600+. Flag any contractor payments that need a 1099 form
- Receipt threshold: no receipt needed under $75, but keep all receipts for items over $75 to substantiate in audit
- Cost of Goods Sold: required if selling physical products (inventory). Not applicable for service businesses
- Health insurance: self-employed health insurance is deducted on Form 1040 (not Schedule C)