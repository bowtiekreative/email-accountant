"""FastAPI service for the Email Accountant webapp.

Thin HTTP layer over the existing SQLite ledger + scan pipeline. Run with:

    uvicorn app.main:app --reload --port 8000
"""

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import ledger, planning, reminders, scans
from .config import FRONTEND_ORIGIN

app = FastAPI(title="Email Accountant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "years": ledger.available_years()}


@app.get("/api/years")
def years() -> list[int]:
    return ledger.available_years()


@app.get("/api/overview")
def overview(year: Optional[int] = None, currency: Optional[str] = None) -> dict[str, Any]:
    return ledger.overview(year=year, currency=currency)


@app.get("/api/currencies")
def currencies() -> list[str]:
    return ledger.available_currencies()


@app.get("/api/transactions")
def transactions(
    year: Optional[int] = None,
    domain: Optional[str] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    needs_review: Optional[bool] = None,
    currency: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return ledger.list_transactions(
        year=year,
        domain=domain,
        tx_type=type,
        category=category,
        q=q,
        needs_review=needs_review,
        currency=currency,
        limit=limit,
        offset=offset,
    )


class TransactionUpdate(BaseModel):
    domain: Optional[str] = None
    transaction_type: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    tax_category: Optional[str] = None
    merchant_name: Optional[str] = None
    amount: Optional[float] = None
    is_deductible: Optional[bool] = None
    deduction_rate: Optional[float] = None
    needs_review: Optional[bool] = None
    reviewed: Optional[bool] = None
    flagged: Optional[bool] = None
    flag_reason: Optional[str] = None


@app.patch("/api/transactions/{composite_id}")
def update_transaction(composite_id: str, payload: TransactionUpdate) -> dict[str, Any]:
    changes = payload.model_dump(exclude_none=True)
    try:
        return ledger.update_transaction(composite_id, changes)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/categories")
def categories() -> list[dict[str, Any]]:
    return ledger.list_categories()


@app.get("/api/reports/schedule-c")
def schedule_c(year: int, currency: str = "USD") -> dict[str, Any]:
    return ledger.schedule_c(year, currency=currency)


@app.get("/api/reports/t2125")
def t2125(year: int, currency: str = "CAD") -> dict[str, Any]:
    return ledger.t2125(year, currency=currency)


@app.get("/api/reports/gst-hst")
def gst_hst(year: int, currency: str = "CAD") -> dict[str, Any]:
    return ledger.gst_hst(year, currency=currency)


@app.get("/api/scans")
def scan_runs() -> dict[str, Any]:
    return {
        "history": ledger.scan_history(),
        "current": scans.latest_job(),
    }


@app.post("/api/scans")
def trigger_scan(mode: str = "incremental") -> dict[str, Any]:
    """mode=incremental (recent) or mode=full (history back to START_YEAR)."""
    return scans.start_scan(mode=mode)


@app.get("/api/scans/{job_id}")
def scan_status(job_id: str) -> dict[str, Any]:
    job = scans.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Planning suite: subscriptions, budgets, recommendations, yearly plan
# ---------------------------------------------------------------------------

@app.get("/api/subscriptions")
def subscriptions(currency: Optional[str] = None) -> dict[str, Any]:
    return planning.subscriptions(currency=currency)


@app.get("/api/budgets")
def budgets() -> list[dict[str, Any]]:
    return planning.list_budgets()


class BudgetIn(BaseModel):
    category: str
    monthly_limit: float
    currency: str = "USD"
    domain: Optional[str] = None


@app.post("/api/budgets")
def set_budget(payload: BudgetIn) -> dict[str, Any]:
    return planning.set_budget(
        payload.category, payload.monthly_limit, payload.currency, payload.domain
    )


@app.delete("/api/budgets")
def delete_budget(category: str, currency: str = "USD") -> dict[str, Any]:
    planning.delete_budget(category, currency)
    return {"deleted": category, "currency": currency}


@app.get("/api/budgets/recommendations")
def budget_recommendations(currency: str = "USD") -> dict[str, Any]:
    return planning.budget_recommendations(currency=currency)


@app.post("/api/budgets/apply-recommendations")
def apply_recommendations(currency: str = "USD") -> dict[str, Any]:
    return planning.apply_recommended_budgets(currency=currency)


@app.get("/api/plan")
def yearly_plan(year: int, currency: str = "USD") -> dict[str, Any]:
    return planning.yearly_plan(year, currency=currency)


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

@app.get("/api/reminders")
def list_reminders(currency: Optional[str] = None) -> list[dict[str, Any]]:
    return reminders.build_reminders(currency=currency)


@app.post("/api/reminders/send")
def send_reminders(currency: Optional[str] = None) -> dict[str, Any]:
    return reminders.send_reminders(currency=currency)


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

@app.post("/api/backup")
def backup() -> dict[str, Any]:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from scripts.backup_ledgers import backup as run_backup

    dest = run_backup()
    return {"backed_up_to": str(dest), "files": len(list(dest.glob("*.db")))}
