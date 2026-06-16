#!/usr/bin/env python3
"""Send the reminders digest by email. Intended for a daily cron job.

    python reminders_cron.py

Requires SMTP settings (SMTP_HOST/SMTP_USER/SMTP_PASS/REMINDER_TO) or a Gmail
app password (GMAIL_USER/GMAIL_APP_PASSWORD). Prints the result.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "webapp" / "backend"))

from app import reminders  # noqa: E402

if __name__ == "__main__":
    result = reminders.send_reminders()
    if result.get("sent"):
        print(f"✅ Sent {result['count']} reminder(s) to {result['to']}")
    else:
        print(f"ℹ️  Not sent: {result.get('reason')} ({result.get('count', 0)} reminder(s))")
        for r in result.get("reminders", []):
            print(f"   • [{r['severity']}] {r['message']}")
