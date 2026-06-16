#!/usr/bin/env bash
# Wrapper that runs the full archive scan and logs to a file
set -e
LOGFILE="$HOME/.email-accountant/archive_scan_$(date +%Y%m%d_%H%M%S).log"
echo "=== Archive scan started at $(date) ===" | tee "$LOGFILE"
cd /opt/data/email-accountant
PYTHONUNBUFFERED=1 python3 -u run_full_archive.py 2>&1 | tee -a "$LOGFILE"
echo "=== Archive scan finished at $(date) ===" | tee -a "$LOGFILE"
