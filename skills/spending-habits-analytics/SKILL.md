---
name: spending-habits-analytics
description: "Analyze spending patterns, generate financial insights, and create visual reports. Track trends by category, merchant, and time period with budget comparisons."
domain: financial
tags:
  - analytics
  - spending
  - reports
  - visualization
  - budgets
  - trends
---

# Spending Habits & Analytics

## Overview

Analyze categorized transactions to produce actionable financial insights: monthly spending breakdowns, category trends, income vs expense tracking, recurring pattern detection, and budget adherence reporting.

## Monthly Spending Report

```python
import sqlite3
from datetime import datetime
from collections import defaultdict

def monthly_report(year, month, base_dir='data'):
    """Generate a comprehensive monthly report."""
    conn = sqlite3.connect(get_db_path(year, base_dir))
    conn.row_factory = sqlite3.Row
    month_str = f"{year}-{month:02d}"
    
    report = {
        'period': month_str,
        'income': {'total': 0, 'by_category': {}, 'by_domain': {'personal': 0, 'business': 0}},
        'expenses': {'total': 0, 'by_category': {}, 'by_domain': {'personal': 0, 'business': 0}},
        'net': 0,
        'top_merchants': [],
        'recurring': [],
        'flags': [],
    }
    
    # Total income
    rows = conn.execute('''
        SELECT domain, category, SUM(amount) as total, COUNT(*) as count
        FROM transactions 
        WHERE strftime('%Y-%m', email_date) = ? AND type = 'income'
        GROUP BY domain, category
        ORDER BY total DESC
    ''', (month_str,)).fetchall()
    
    for row in rows:
        report['income']['total'] += row['total']
        report['income']['by_domain'][row['domain']] += row['total']
        report['income']['by_category'][row['category']] = {
            'amount': row['total'],
            'count': row['count']
        }
    
    # Total expenses
    rows = conn.execute('''
        SELECT domain, category, SUM(amount) as total, COUNT(*) as count
        FROM transactions 
        WHERE strftime('%Y-%m', email_date) = ? AND type = 'expense'
        GROUP BY domain, category
        ORDER BY total DESC
    ''', (month_str,)).fetchall()
    
    for row in rows:
        report['expenses']['total'] += row['total']
        report['expenses']['by_domain'][row['domain']] += row['total']
        report['expenses']['by_category'][row['category']] = {
            'amount': row['total'],
            'count': row['count']
        }
    
    report['net'] = report['income']['total'] - report['expenses']['total']
    
    # Top merchants
    rows = conn.execute('''
        SELECT merchant_name, SUM(amount) as total, COUNT(*) as count
        FROM transactions
        WHERE strftime('%Y-%m', email_date) = ?
        GROUP BY merchant_name
        ORDER BY total DESC
        LIMIT 10
    ''', (month_str,)).fetchall()
    report['top_merchants'] = [dict(r) for r in rows]
    
    # Detect recurring
    report['recurring'] = detect_recurring(year, month)
    
    # Flags (anomalies)
    if report['expenses']['total'] > report['income']['total'] * 2:
        report['flags'].append('⚠️ Expenses exceed 2x income — risk of deficit')
    if report['expenses']['by_domain'].get('personal', 0) > report['income']['by_domain'].get('personal', 0) * 1.5:
        report['flags'].append('⚠️ Personal spending exceeds personal income — check lifestyle creep')
    if not report['income']['total']:
        report['flags'].append('⚠️ No income detected this month')
    
    return report
```

## Yearly Summary

```python
def yearly_summary(year, base_dir='data'):
    """Generate year-to-date financial summary."""
    conn = sqlite3.connect(get_db_path(year, base_dir))
    conn.row_factory = sqlite3.Row
    
    # Monthly income/expense series
    monthly = conn.execute('''
        SELECT strftime('%m', email_date) as month,
               SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
               SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
        FROM transactions
        GROUP BY month
        ORDER BY month
    ''').fetchall()
    
    # Category breakdown
    categories = conn.execute('''
        SELECT category, type, SUM(amount) as total, COUNT(*) as count,
               ROUND(AVG(amount), 2) as avg_amount
        FROM transactions
        WHERE type = 'expense' AND domain = 'business'
        GROUP BY category
        ORDER BY total DESC
    ''').fetchall()
    
    # Tax-deductible total
    deductible = conn.execute('''
        SELECT SUM(amount * deduction_rate) as deductible_total
        FROM transactions
        WHERE is_deductible = 1
    ''').fetchone()['deductible_total'] or 0
    
    return {
        'year': year,
        'monthly_series': [dict(r) for r in monthly],
        'category_breakdown': [dict(r) for r in categories],
        'total_deductible': round(deductible, 2),
        'total_income': sum(r['income'] for r in monthly),
        'total_expenses': sum(r['expenses'] for r in monthly),
        'net': sum(r['income'] - r['expenses'] for r in monthly),
    }
```

## Recurring Transaction Detection

```python
def detect_recurring(year, base_dir='data'):
    """Detect recurring transactions (subscriptions, regular bills)."""
    conn = sqlite3.connect(get_db_path(year, base_dir))
    conn.row_factory = sqlite3.Row
    
    # Find merchants with same amount appearing 3+ times in the year
    recurring = conn.execute('''
        SELECT merchant_name, ROUND(amount, 2) as amt, 
               COUNT(*) as occurrences,
               GROUP_CONCAT(strftime('%Y-%m', email_date)) as months
        FROM transactions
        WHERE type = 'expense'
        GROUP BY merchant_name, ROUND(amount, 2)
        HAVING occurrences >= 3
        ORDER BY occurrences DESC
    ''').fetchall()
    
    results = []
    for r in recurring:
        months_active = r['occurrences']
        estimated_annual = r['amt'] * 12
        
        results.append({
            'merchant': r['merchant_name'],
            'amount': r['amt'],
            'frequency': months_active,
            'estimated_annual': estimated_annual,
            'months_seen': r['months'],
        })
    
    return results
```

## Spending Trends & Patterns

```python
def spending_trends(year, base_dir='data'):
    """Analyze spending trends over the year."""
    conn = sqlite3.connect(get_db_path(year, base_dir))
    conn.row_factory = sqlite3.Row
    
    # Category spending over time
    category_trends = conn.execute('''
        SELECT category, strftime('%m', email_date) as month, 
               SUM(amount) as total
        FROM transactions
        WHERE type = 'expense'
        GROUP BY category, month
        ORDER BY category, month
    ''').fetchall()
    
    # Detect increasing categories
    trends = defaultdict(list)
    for row in category_trends:
        trends[row['category']].append(row)
    
    risings = []
    for cat, data in trends.items():
        if len(data) >= 3:
            values = [d['total'] for d in data]
            if values[-1] > values[0] * 1.5:  # 50%+ increase
                risings.append(cat)
    
    # Business vs Personal ratio
    ratio = conn.execute('''
        SELECT strftime('%m', email_date) as month,
               SUM(CASE WHEN domain = 'business' AND type = 'expense' THEN amount ELSE 0 END) as biz,
               SUM(CASE WHEN domain = 'personal' AND type = 'expense' THEN amount ELSE 0 END) as pers
        FROM transactions
        GROUP BY month
        ORDER BY month
    ''').fetchall()
    
    return {
        'top_categories': extract_top_categories(conn, year),
        'rising_categories': risings,
        'biz_personal_ratio': [dict(r) for r in ratio],
        'monthly_average': conn.execute('''
            SELECT ROUND(AVG(total), 2) as avg_monthly
            FROM (
                SELECT strftime('%m', email_date) as month, SUM(amount) as total
                FROM transactions WHERE type = 'expense'
                GROUP BY month
            )
        ''').fetchone()['avg_monthly'],
    }


def extract_top_categories(conn, year):
    """Get top spending categories for the year."""
    rows = conn.execute('''
        SELECT category, SUM(amount) as total, COUNT(*) as count
        FROM transactions
        WHERE type = 'expense' AND category IS NOT NULL
        GROUP BY category
        ORDER BY total DESC
        LIMIT 15
    ''').fetchall()
    return [dict(r) for r in rows]
```

## Visual Report (HTML)

```python
def generate_html_report(year, base_dir='data', output_path=None):
    """Generate a self-contained HTML financial report."""
    yearly = yearly_summary(year, base_dir)
    trends = spending_trends(year, base_dir)
    recurring = detect_recurring(year, base_dir)
    
    if not output_path:
        output_path = f'financial_report_{year}.html'
    
    html = f"""
    <!DOCTYPE html><html><head>
    <meta charset="utf-8"><title>Financial Report {year}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: auto; padding: 20px; background: #0f0f1a; color: #e0e0e0; }}
        h1 {{ color: #00d4aa; }} h2 {{ color: #8888ff; border-bottom: 1px solid #333; }}
        .card {{ background: #1a1a2e; padding: 16px; border-radius: 8px; margin: 12px 0; }}
        .amt {{ color: #00d4aa; font-weight: bold; }}
        .neg {{ color: #ff5555; }}
        .good {{ color: #50fa7b; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td, th {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
    </style></head><body>
    <h1>📊 Financial Report {year}</h1>
    
    <div class="summary-grid">
        <div class="card">
            <h3>Total Income</h3>
            <div class="amt">${yearly['total_income']:,.2f}</div>
        </div>
        <div class="card">
            <h3>Total Expenses</h3>
            <div class="neg">${yearly['total_expenses']:,.2f}</div>
        </div>
        <div class="card">
            <h3>Net</h3>
            <div class="{'good' if yearly['net'] >= 0 else 'neg'}">${yearly['net']:,.2f}</div>
        </div>
    </div>
    
    <div class="card">
        <h2>💰 Deductible Expenses</h2>
        <p>Total tax-deductible: <span class="good">${yearly['total_deductible']:,.2f}</span></p>
    </div>
    
    <div class="card">
        <h2>🏷️ Top Spending Categories</h2>
        <table><tr><th>Category</th><th>Total</th><th>Count</th><th>Avg</th></tr>
    """
    
    for cat in yearly['category_breakdown']:
        html += f"<tr><td>{cat['category']}</td><td>${cat['total']:,.2f}</td><td>{cat['count']}</td><td>${cat['avg_amount']}</td></tr>"
    
    html += "</table></div>"
    
    if recurring:
        html += """
        <div class="card"><h2>🔄 Recurring Charges</h2><table>
        <tr><th>Merchant</th><th>Amount</th><th>Occurrences</th><th>Estimated Annual</th></tr>
        """
        for r in recurring:
            html += f"<tr><td>{r['merchant']}</td><td>${r['amount']:.2f}</td><td>{r['frequency']}</td><td>${r['estimated_annual']:.2f}</td></tr>"
        html += "</table></div>"
    
    if trends['rising_categories']:
        html += f"""
        <div class="card"><h2>📈 Rising Categories</h2>
        <p>These categories increased 50%+ over the year:</p>
        <ul>{"".join(f'<li>{c}</li>' for c in trends['rising_categories'])}</ul></div>
        """
    
    html += "</body></html>"
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path
```

## Budget Tracking

```python
BUDGETS = {
    'Software & Subscriptions': {'monthly': 200, 'annual': 2400},
    'Marketing & Advertising': {'monthly': 500, 'annual': 6000},
    'Dining Out': {'monthly': 300, 'annual': 3600},
}

def budget_check(year, month, base_dir='data'):
    """Compare actual spending against budgets."""
    report = monthly_report(year, month, base_dir)
    alerts = []
    
    for category, budget in BUDGETS.items():
        actual = report['expenses']['by_category'].get(category, {}).get('amount', 0)
        if actual > budget['monthly']:
            pct = (actual / budget['monthly']) * 100
            alerts.append({
                'category': category,
                'budget': budget['monthly'],
                'actual': round(actual, 2),
                'pct': round(pct),
                'status': 'over' if pct > 100 else 'approaching'
            })
    
    return alerts
```

## GOTCHAs

- Year-partitioned DB: cross-year queries (e.g. "last 12 months across two years") need separate DB access
- Merchant name normalization: "AMZN MKTP US" and "Amazon.com" are the same merchant. Populate merchant_aliases table
- Rounding: amounts are REAL (float). Round to 2 decimals for display, keep full precision for calculations
- Empty months: if a month has no transactions, the monthly series will have a gap. Fill with zeros for charts
- Recurring detection needs at least 3 months of data to be reliable — don't flag 2-time occurrences