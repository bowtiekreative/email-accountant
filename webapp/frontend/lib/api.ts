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

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

export const api = {
  base: API_BASE,
  years: () => get<number[]>("/api/years"),
  currencies: () => get<string[]>("/api/currencies"),
  overview: (year?: number, currency?: string) => {
    const qs = new URLSearchParams();
    if (year) qs.set("year", String(year));
    if (currency) qs.set("currency", currency);
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
  async startScan() {
    const res = await fetch(`${API_BASE}/api/scans`, { method: "POST" });
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
