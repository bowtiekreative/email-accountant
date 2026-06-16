"""
Full Archive Scan — scan ALL financial emails from Gmail (no date limit)
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner.gmail_scanner import GmailScanner
from db.database import EmailAccountantDB, init_sqlite
from datetime import datetime
from pathlib import Path
import shutil

# Backup existing DB
DB_DIR = Path.home() / ".email-accountant" / "data"
BACKUP_DIR = Path.home() / ".email-accountant" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

yr = datetime.now().year
current_db = DB_DIR / f"email_accountant_{yr}.db"

if current_db.exists():
    backup_name = f"email_accountant_{yr}_pre_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(current_db, BACKUP_DIR / backup_name)
    print(f"📦 Backed up existing DB → {BACKUP_DIR / backup_name}")
    current_db.unlink()
    print(f"🗑️  Removed old DB to start fresh")

# Initialize fresh DB
init_sqlite(yr)
db = EmailAccountantDB(yr)

# Scan ALL mail (no date limit)
scanner = GmailScanner(db)
try:
    scanner.connect()
    results = scanner.scan_and_store(
        days_back=None, 
        folder='"[Gmail]/All Mail"'
    )
    
    print(f"\n{'='*60}")
    print(f"📊 FULL ARCHIVE SCAN COMPLETE: {len(results)} emails stored")
    print(f"{'='*60}")
    
    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_emails": len(results),
    }
    report_path = Path.home() / ".email-accountant" / "archive_scan_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"📄 Report saved to {report_path}")
    
finally:
    scanner.disconnect()
    db.close()
