# FastAPI backend for the dashboard. Build context is the REPO ROOT, because the
# API imports the scanner engine (db/, pipeline/, accounts.py, scan_*.py).
#   docker build -f webapp/backend/Dockerfile .

FROM python:3.11-slim
WORKDIR /app

# System deps kept minimal; OCR/scan extras are only needed if you run scans
# inside this container (optional).
COPY webapp/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bits the API needs from the repo root.
COPY db ./db
COPY pipeline ./pipeline
COPY reconciliation ./reconciliation
COPY accounts.py ./accounts.py
COPY scan_daily.py scan_full_archive_fast.py ./
COPY webapp/backend ./webapp/backend

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
# Ledger data is mounted here (see docker-compose).
ENV EMAIL_ACCOUNTANT_DB_DIR=/data
ENV EMAIL_ACCOUNTANT_HOME=/config

WORKDIR /app/webapp/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
