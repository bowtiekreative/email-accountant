#!/usr/bin/env python3
"""Run the Gmail financial email scanner."""
import os, sys, subprocess, json
from datetime import datetime

# Get Gmail app password from Proton Pass
os.environ['PATH'] = f"{os.path.expanduser('~/.local/bin')}:{os.environ.get('PATH', '')}"
os.environ['PROTON_PASS_KEY_PROVIDER'] = 'fs'
os.environ['PROTON_PASS_SESSION_DIR'] = '/tmp/pass-agent-hermes'

result = subprocess.run(
    ['pass-cli', 'item', 'view', '--vault-name', 'Messaging',
     '--item-title', 'Gmail ryan@bowtiekreative.com', '--field', 'App Password'],
    capture_output=True, text=True,
    env={**os.environ, 'PROTON_PASS_AGENT_REASON': 'Retrieving Gmail app password for email scanning'}
)
gmail_password = result.stdout.strip()

# Set up scanner module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scanner.gmail_scanner
import importlib
importlib.reload(scanner.gmail_scanner)
scanner.gmail_scanner.GMAIL_APP_PASSWORD = gmail_password
scanner.gmail_scanner.GMAIL_USER = "ryan@bowtiekreative.com"

from db.database import EmailAccountantDB, init_sqlite

yr = datetime.now().year
init_sqlite(yr)
db = EmailAccountantDB(yr)

scanner_inst = scanner.gmail_scanner.GmailScanner(db)
try:
    scanner_inst.connect()
    print('✅ Connected to Gmail as ryan@bowtiekreative.com')

    results = scanner_inst.scan_and_store(days_back=90, folder='"[Gmail]/All Mail"')

    print(f'\n📊 SCAN RESULTS:')
    print(f'   Total financial emails stored: {len(results)}')
    for r in results[:25]:
        print(f'   • {r["from"]:35s} | {r["subject"][:55]}')
    if len(results) > 25:
        print(f'   ... and {len(results)-25} more')

    emails = db.search_emails("")
    print(f'\n📊 Database: {len(emails)} emails')

    att_dir = os.path.expanduser('~/.email-accountant/attachments')
    if os.path.exists(att_dir):
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(att_dir):
            for f in files:
                fp = os.path.join(root, f)
                total_size += os.path.getsize(fp)
                file_count += 1
        print(f'   Attachments archived: {file_count} files ({total_size/1024:.0f} KB)')

    # Save report
    report = {"timestamp": datetime.now().isoformat(), "count": len(results), "emails": results}
    report_dir = os.path.expanduser('~/.email-accountant')
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, 'latest_scan.json'), 'w') as f:
        json.dump(report, f, indent=2)
    print(f'\n📄 Report saved')

finally:
    scanner_inst.disconnect()
    db.close()
