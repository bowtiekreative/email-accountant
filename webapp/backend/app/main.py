"""FastAPI service for the Email Accountant webapp.

Thin HTTP layer over the existing SQLite ledger + scan pipeline. Run with:

    uvicorn app.main:app --reload --port 8000
"""

from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import (
    accounts, assistant, auth, invest, learning, ledger, networth, planning,
    reminders, scans, stack_settings, stack_sync, supabase_auth,
)
from .config import FRONTEND_ORIGIN

app = FastAPI(title="Ledger API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints reachable without a session token.
_PUBLIC_PATHS = {"/api/health", "/api/auth/login"}


def _resolve_user(token: str) -> Optional[str]:
    """Accept a Supabase access token (verified via JWKS) or the legacy token."""
    if supabase_auth.supabase_auth_enabled():
        user = supabase_auth.user_from_token(token)
        if user:
            return user
    return auth.verify_token(token)


@app.middleware("http")
async def require_login(request: Request, call_next):
    """Gate every /api/* route behind a valid session token."""
    path = request.url.path
    if (
        path.startswith("/api/")
        and path not in _PUBLIC_PATHS
        and request.method != "OPTIONS"
    ):
        token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        if not _resolve_user(token):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


def current_user(authorization: str = Header(default="")) -> str:
    user = _resolve_user((authorization or "").removeprefix("Bearer ").strip())
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(payload: LoginIn) -> dict[str, Any]:
    if not auth.verify(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"token": auth.make_token(payload.username), "username": payload.username}


@app.get("/api/auth/me")
def auth_me(authorization: str = Header(default="")) -> dict[str, Any]:
    user = current_user(authorization)
    return {"username": user, "email": user if "@" in user else None}


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordIn, authorization: str = Header(default="")) -> dict[str, Any]:
    user = current_user(authorization)
    try:
        if not auth.change_password(user, payload.old_password, payload.new_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"changed": True}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "years": ledger.available_years(),
        "supabase_auth": supabase_auth.supabase_auth_enabled(),
        "assistant": assistant.assistant_enabled(),
    }


# ---------------------------------------------------------------------------
# Ask AI — spending assistant (Claude)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    messages: list[ChatMessage]
    currency: str = "USD"


@app.post("/api/assistant/chat")
def assistant_chat(payload: ChatIn) -> dict[str, Any]:
    try:
        return assistant.chat(
            [m.model_dump() for m in payload.messages], currency=payload.currency
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # pragma: no cover - upstream/network errors
        raise HTTPException(status_code=502, detail=f"Assistant error: {exc}")


@app.get("/api/years")
def years() -> list[int]:
    return ledger.available_years()


@app.get("/api/overview")
def overview(year: Optional[int] = None, currency: Optional[str] = None,
             account: Optional[str] = None) -> dict[str, Any]:
    return ledger.overview(year=year, currency=currency, account=account)


@app.get("/api/currencies")
def currencies() -> list[str]:
    return ledger.available_currencies()


@app.get("/api/account-list")
def account_list() -> list[str]:
    """Account labels that appear in the ledger (for the per-account filter)."""
    return ledger.available_accounts()


@app.get("/api/transactions")
def transactions(
    year: Optional[int] = None,
    domain: Optional[str] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    needs_review: Optional[bool] = None,
    currency: Optional[str] = None,
    account: Optional[str] = None,
    state: Optional[str] = None,
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
        account=account,
        state=state,
        limit=limit,
        offset=offset,
    )


@app.get("/api/transactions/count")
def transactions_count(
    year: Optional[int] = None,
    domain: Optional[str] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    needs_review: Optional[bool] = None,
    currency: Optional[str] = None,
    account: Optional[str] = None,
    state: Optional[str] = None,
) -> dict[str, int]:
    return {"total": ledger.count_transactions(
        year=year, domain=domain, tx_type=type, category=category, q=q,
        needs_review=needs_review, currency=currency, account=account, state=state,
    )}


@app.get("/api/transactions/{composite_id}/detail")
def transaction_detail(composite_id: str) -> dict[str, Any]:
    try:
        return ledger.transaction_detail(composite_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class DeleteIn(BaseModel):
    ids: list[str]


@app.post("/api/transactions/delete")
def delete_transactions(payload: DeleteIn) -> dict[str, int]:
    return {"deleted": ledger.delete_transactions(payload.ids)}


@app.post("/api/transactions/clear")
def clear_transactions() -> dict[str, Any]:
    return ledger.clear_all()


@app.post("/api/transactions/reprocess")
def reprocess_transactions() -> dict[str, Any]:
    return ledger.reprocess_all()


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
    txn_state: Optional[str] = None


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


@app.get("/api/learned-rules")
def learned_rules() -> list[dict[str, Any]]:
    return learning.list_rules()


# ---------------------------------------------------------------------------
# Email accounts (Gmail + IMAP) — managed in the Accounts screen
# ---------------------------------------------------------------------------

@app.get("/api/accounts")
def get_accounts() -> list[dict[str, Any]]:
    return accounts.list_accounts()


class AccountIn(BaseModel):
    label: str
    email: str
    provider: str = "gmail"
    password: Optional[str] = None
    password_env: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None


@app.post("/api/accounts")
def add_account(payload: AccountIn) -> dict[str, Any]:
    try:
        return accounts.add_account(
            label=payload.label, email=payload.email, provider=payload.provider,
            password=payload.password, password_env=payload.password_env,
            imap_host=payload.imap_host, imap_port=payload.imap_port,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class AccountPatch(BaseModel):
    email: Optional[str] = None
    provider: Optional[str] = None
    password: Optional[str] = None
    password_env: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    active: Optional[bool] = None


@app.patch("/api/accounts/{label}")
def update_account(label: str, payload: AccountPatch) -> dict[str, Any]:
    try:
        return accounts.update_account(label, **payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/accounts/{label}")
def delete_account(label: str) -> dict[str, Any]:
    return accounts.delete_account(label)


# ---------------------------------------------------------------------------
# Stack connections (Paperless / Akaunting / Firefly / Strapi)
# ---------------------------------------------------------------------------

@app.get("/api/stack/config")
def stack_config() -> dict[str, Any]:
    return stack_settings.public_view()


@app.put("/api/stack/config/{service}")
def stack_config_update(service: str, fields: dict[str, Any]) -> dict[str, Any]:
    try:
        return stack_settings.update(service, fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/stack/test/{service}")
def stack_test(service: str) -> dict[str, Any]:
    return stack_settings.test(service)


@app.get("/api/stack/sync")
def stack_sync_status() -> dict[str, Any]:
    return stack_sync.status()


@app.post("/api/stack/sync")
def stack_sync_start(force: bool = False) -> dict[str, Any]:
    return stack_sync.start(force=force)


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


@app.post("/api/scans/stop")
def stop_scan() -> dict[str, Any]:
    return scans.stop_scan()


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
# Invest / wealth suite
# ---------------------------------------------------------------------------

@app.get("/api/invest/advice")
def invest_advice(currency: str = "USD") -> dict[str, Any]:
    return invest.wealth_advice(currency=currency)


class CompoundIn(BaseModel):
    principal: float = 0.0
    monthly_contribution: float = 0.0
    annual_rate: float = 0.08
    years: int = 20


@app.post("/api/invest/compound")
def invest_compound(payload: CompoundIn) -> dict[str, Any]:
    return invest.compound_growth(
        payload.principal, payload.monthly_contribution,
        payload.annual_rate, payload.years,
    )


@app.get("/api/invest/fire")
def invest_fire(annual_expense: float, withdrawal_rate: float = 0.04) -> dict[str, Any]:
    return invest.fire_number(annual_expense, withdrawal_rate)


# ---------------------------------------------------------------------------
# Net worth
# ---------------------------------------------------------------------------

@app.get("/api/networth/accounts")
def networth_accounts() -> list[dict[str, Any]]:
    return networth.list_accounts()


class NetWorthAccountIn(BaseModel):
    name: str
    kind: str  # asset | liability
    category: str = ""
    currency: str = "USD"
    institution: str = ""
    balance: Optional[float] = None


@app.post("/api/networth/accounts")
def networth_add_account(payload: NetWorthAccountIn) -> dict[str, Any]:
    try:
        return networth.add_account(
            name=payload.name, kind=payload.kind, category=payload.category,
            currency=payload.currency, institution=payload.institution,
            balance=payload.balance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/networth/accounts/{account_id}")
def networth_delete_account(account_id: int) -> dict[str, Any]:
    networth.delete_account(account_id)
    return {"deleted": account_id}


class SnapshotIn(BaseModel):
    account_id: int
    balance: float
    as_of: Optional[str] = None


@app.post("/api/networth/snapshots")
def networth_snapshot(payload: SnapshotIn) -> dict[str, Any]:
    return networth.record_snapshot(payload.account_id, payload.balance, payload.as_of)


@app.get("/api/networth/summary")
def networth_summary(currency: str = "USD") -> dict[str, Any]:
    return networth.summary(currency=currency)


@app.get("/api/networth/history")
def networth_history(currency: str = "USD") -> list[dict[str, Any]]:
    return networth.history(currency=currency)


@app.get("/api/networth/projection")
def networth_projection(currency: str = "USD", annual_rate: float = 0.07,
                        years: int = 30) -> dict[str, Any]:
    return networth.projection(currency=currency, annual_rate=annual_rate, years=years)


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
