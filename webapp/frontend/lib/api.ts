const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type Bucket = { name: string; total: number; count: number };

export type CurrencyTotals = {
  income: number;
  expense: number;
  net: number;
  business_expense: number;
  deductible: number;
  transaction_count: number;
};

export type Overview = {
  year: number | null;
  currencies: string[];
  active_currency: string;
  totals_by_currency: Record<string, CurrencyTotals>;
  needs_review: number;
  by_category: Bucket[];
  by_merchant: Bucket[];
  by_domain: Bucket[];
  monthly_trend: { month: string; income: number; expense: number }[];
};

export type Transaction = {
  id: string;
  email_subject?: string;
  email_date?: string;
  merchant_name?: string;
  amount?: number;
  currency: string;
  domain?: string;
  transaction_type?: string;
  category?: string;
  tax_category?: string;
  is_deductible?: number;
  deduction_rate?: number;
  needs_review?: number;
  reviewed?: number;
  classification_confidence?: number;
  classification_method?: string;
  account?: string;
};

export type TransactionPatch = {
  domain?: string;
  transaction_type?: string;
  category?: string;
  subcategory?: string;
  tax_category?: string;
  merchant_name?: string;
  amount?: number;
  is_deductible?: boolean;
  deduction_rate?: number;
  needs_review?: boolean;
  reviewed?: boolean;
  flagged?: boolean;
  flag_reason?: string;
};

export type Category = {
  name: string;
  domain?: string;
  tx_type?: string;
  irs_line?: string;
};

export type TaxLine = {
  line: string;
  total: number;
  deductible: number;
  count: number;
};

export type TaxReport = {
  year: number;
  currency: string;
  form: string;
  gross_income: number;
  total_expenses: number;
  total_deductible: number;
  net_profit: number;
  income: TaxLine[];
  expenses: TaxLine[];
};

export type GstHst = {
  year: number;
  currency: string;
  taxable_sales: number;
  sales_count: number;
  eligible_expenses: number;
  expense_count: number;
  note: string;
};

export type Subscription = {
  merchant: string;
  currency: string;
  category?: string;
  domain?: string;
  frequency: string;
  typical_amount: number;
  monthly_cost: number;
  annual_cost: number;
  charges: number;
  last_charge: string;
  active: boolean;
};

export type SubscriptionsResponse = {
  subscriptions: Subscription[];
  monthly_burn_by_currency: Record<string, number>;
  active_count: number;
};

export type Budget = {
  category: string;
  monthly_limit: number;
  annual_limit?: number;
  currency: string;
  domain?: string;
};

export type Recommendation = {
  category: string;
  currency: string;
  avg_monthly: number;
  peak_monthly: number;
  recommended_monthly: number;
  current_budget: number | null;
  status: string;
};

export type YearlyPlan = {
  year: number;
  currency: string;
  months_elapsed: number;
  actual_income: number;
  actual_expense: number;
  actual_net: number;
  projected_income: number;
  projected_expense: number;
  projected_net: number;
  budgeted_annual_expense: number;
  categories: { category: string; spent: number; annual_budget: number | null; over: boolean }[];
};

export type Reminder = {
  type: string;
  severity: "high" | "medium" | "low";
  currency: string | null;
  message: string;
};

export type CompoundResult = {
  principal: number;
  monthly_contribution: number;
  annual_rate: number;
  years: number;
  future_value: number;
  total_contributed: number;
  total_growth: number;
  series: { year: number; balance: number; contributed: number; growth: number }[];
};

export type WealthAdvice = {
  currency: string;
  cashflow: {
    months: number;
    monthly_income: number;
    monthly_expense: number;
    monthly_surplus: number;
    monthly_discretionary: number;
    annual_expense: number;
    top_discretionary: { category: string; monthly: number }[];
  };
  active_subscription_burn: number;
  inactive_subscription_monthly: number;
  recommended_monthly_investment: number;
  fire: { annual_expense: number; withdrawal_rate: number; fire_number: number; note: string };
  years_to_financial_independence: number | null;
  tips: { title: string; severity: string; body: string }[];
  principles: string[];
  disclaimer: string;
};

export type EmailAccount = {
  label: string;
  email: string;
  provider: string;
  imap_host?: string;
  imap_port?: number;
  active: boolean;
  has_password: boolean;
  password_source?: string | null;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

export const api = {
  base: API_BASE,
  years: () => get<number[]>("/api/years"),
  currencies: () => get<string[]>("/api/currencies"),
  accountList: () => get<string[]>("/api/account-list"),
  overview: (year?: number, currency?: string, account?: string) => {
    const qs = new URLSearchParams();
    if (year) qs.set("year", String(year));
    if (currency) qs.set("currency", currency);
    if (account) qs.set("account", account);
    return get<Overview>(`/api/overview?${qs.toString()}`);
  },
  transactions: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    });
    return get<Transaction[]>(`/api/transactions?${qs.toString()}`);
  },
  categories: () => get<Category[]>("/api/categories"),
  accounts: () => get<EmailAccount[]>("/api/accounts"),
  async addAccount(payload: {
    label: string;
    email: string;
    provider: string;
    password?: string;
    imap_host?: string;
    imap_port?: number;
  }) {
    const res = await fetch(`${API_BASE}/api/accounts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "add failed");
    return res.json();
  },
  async toggleAccount(label: string, active: boolean) {
    const res = await fetch(`${API_BASE}/api/accounts/${label}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active }),
    });
    return res.json();
  },
  async deleteAccount(label: string) {
    const res = await fetch(`${API_BASE}/api/accounts/${label}`, { method: "DELETE" });
    return res.json();
  },
  scheduleC: (year: number, currency = "USD") =>
    get<TaxReport>(`/api/reports/schedule-c?year=${year}&currency=${currency}`),
  t2125: (year: number, currency = "CAD") =>
    get<TaxReport>(`/api/reports/t2125?year=${year}&currency=${currency}`),
  gstHst: (year: number, currency = "CAD") =>
    get<GstHst>(`/api/reports/gst-hst?year=${year}&currency=${currency}`),
  scans: () =>
    get<{ history: any[]; current: any }>("/api/scans"),
  async updateTransaction(id: string, changes: TransactionPatch) {
    const res = await fetch(`${API_BASE}/api/transactions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    });
    if (!res.ok) throw new Error(`update failed: ${res.status}`);
    return res.json() as Promise<Transaction>;
  },
  subscriptions: (currency?: string) =>
    get<SubscriptionsResponse>(
      `/api/subscriptions${currency ? `?currency=${currency}` : ""}`
    ),
  budgets: () => get<Budget[]>("/api/budgets"),
  recommendations: (currency = "USD") =>
    get<{ currency: string; recommendations: Recommendation[] }>(
      `/api/budgets/recommendations?currency=${currency}`
    ),
  plan: (year: number, currency = "USD") =>
    get<YearlyPlan>(`/api/plan?year=${year}&currency=${currency}`),
  reminders: (currency?: string) =>
    get<Reminder[]>(`/api/reminders${currency ? `?currency=${currency}` : ""}`),
  wealthAdvice: (currency = "USD") =>
    get<WealthAdvice>(`/api/invest/advice?currency=${currency}`),
  async compound(input: {
    principal: number;
    monthly_contribution: number;
    annual_rate: number;
    years: number;
  }) {
    const res = await fetch(`${API_BASE}/api/invest/compound`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    return res.json() as Promise<CompoundResult>;
  },
  async setBudget(category: string, monthly_limit: number, currency: string) {
    const res = await fetch(`${API_BASE}/api/budgets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, monthly_limit, currency }),
    });
    return res.json();
  },
  async applyRecommendations(currency = "USD") {
    const res = await fetch(
      `${API_BASE}/api/budgets/apply-recommendations?currency=${currency}`,
      { method: "POST" }
    );
    return res.json();
  },
  async backup() {
    const res = await fetch(`${API_BASE}/api/backup`, { method: "POST" });
    return res.json();
  },
  async startScan(mode: "incremental" | "full" = "incremental") {
    const res = await fetch(`${API_BASE}/api/scans?mode=${mode}`, {
      method: "POST",
    });
    return res.json();
  },
};

// Currency-aware. USD -> "$1,000.00", CAD -> "CA$1,000.00" so the two never
// get confused (CAD and USD are tracked separately, never summed together).
export const fmt = (n?: number, currency = "USD") =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    currencyDisplay: "symbol",
  }).format(n ?? 0);
