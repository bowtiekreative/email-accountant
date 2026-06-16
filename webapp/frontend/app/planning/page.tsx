"use client";

import { useEffect, useState } from "react";
import {
  api,
  fmt,
  type Budget,
  type Recommendation,
  type Reminder,
  type SubscriptionsResponse,
  type YearlyPlan,
} from "@/lib/api";
import CurrencyPicker from "@/components/CurrencyPicker";

type Tab = "plan" | "budgets" | "subscriptions" | "reminders";
const TABS: { id: Tab; label: string }[] = [
  { id: "plan", label: "Yearly Plan" },
  { id: "budgets", label: "Budgets" },
  { id: "subscriptions", label: "Subscriptions" },
  { id: "reminders", label: "Reminders" },
];

export default function PlanningPage() {
  const [tab, setTab] = useState<Tab>("plan");
  const [currencies, setCurrencies] = useState<string[]>(["USD"]);
  const [currency, setCurrency] = useState("USD");

  useEffect(() => {
    api.currencies().then((cs) => {
      if (cs.length) {
        setCurrencies(cs);
        setCurrency(cs[0]);
      }
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-ink">Planning</h1>
        <CurrencyPicker currencies={currencies} value={currency} onChange={setCurrency} />
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium transition ${
              tab === t.id
                ? "border-b-2 border-accent text-ink"
                : "text-slate-500 hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "plan" && <PlanTab currency={currency} />}
      {tab === "budgets" && <BudgetsTab currency={currency} />}
      {tab === "subscriptions" && <SubsTab currency={currency} />}
      {tab === "reminders" && <RemindersTab currency={currency} />}
    </div>
  );
}

function Card({ label, value, tone = "default" }: { label: string; value: string; tone?: string }) {
  const cls =
    tone === "good" ? "text-emerald-600" : tone === "bad" ? "text-rose-600" : "text-ink";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${cls}`}>{value}</div>
    </div>
  );
}

function PlanTab({ currency }: { currency: string }) {
  const [data, setData] = useState<YearlyPlan | null>(null);
  const year = new Date().getFullYear();
  useEffect(() => {
    setData(null);
    api.plan(year, currency).then(setData).catch(() => setData(null));
  }, [currency, year]);
  if (!data) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-500">
        {data.year} projection from {data.months_elapsed} month(s) of data, in{" "}
        <strong>{currency}</strong>.
      </p>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card label="Income so far" value={fmt(data.actual_income, currency)} tone="good" />
        <Card label="Spent so far" value={fmt(data.actual_expense, currency)} tone="bad" />
        <Card label="Projected income" value={fmt(data.projected_income, currency)} />
        <Card
          label="Projected net"
          value={fmt(data.projected_net, currency)}
          tone={data.projected_net >= 0 ? "good" : "bad"}
        />
      </div>
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <h2 className="border-b border-slate-100 px-5 py-3 font-semibold text-ink">
          Spending vs budget this year
        </h2>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-5 py-2">Category</th>
              <th className="px-5 py-2 text-right">Spent</th>
              <th className="px-5 py-2 text-right">Annual budget</th>
              <th className="px-5 py-2 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.categories.slice(0, 20).map((c) => (
              <tr key={c.category}>
                <td className="px-5 py-2 text-slate-700">{c.category}</td>
                <td className="px-5 py-2 text-right tabular-nums">{fmt(c.spent, currency)}</td>
                <td className="px-5 py-2 text-right tabular-nums text-slate-500">
                  {c.annual_budget ? fmt(c.annual_budget, currency) : "—"}
                </td>
                <td className="px-5 py-2 text-right">
                  {c.annual_budget ? (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        c.over ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {c.over ? "over" : "on track"}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">no budget</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function BudgetsTab({ currency }: { currency: string }) {
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.recommendations(currency).then((r) => setRecs(r.recommendations)).catch(() => setRecs([]));
  useEffect(() => {
    setRecs(null);
    load();
  }, [currency]);

  async function applyAll() {
    setBusy(true);
    try {
      await api.applyRecommendations(currency);
      await load();
    } finally {
      setBusy(false);
    }
  }
  async function applyOne(r: Recommendation) {
    await api.setBudget(r.category, r.recommended_monthly, currency);
    await load();
  }

  if (!recs) return <div className="text-slate-400">Loading…</div>;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Recommended monthly budgets from your last 12 months ({currency}).
        </p>
        <button
          onClick={applyAll}
          disabled={busy}
          className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
        >
          {busy ? "Applying…" : "Apply all suggestions"}
        </button>
      </div>
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-5 py-2">Category</th>
              <th className="px-5 py-2 text-right">Avg/mo</th>
              <th className="px-5 py-2 text-right">Suggested</th>
              <th className="px-5 py-2 text-right">Current</th>
              <th className="px-5 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {recs.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-slate-400">
                  Not enough history yet.
                </td>
              </tr>
            )}
            {recs.map((r) => (
              <tr key={r.category}>
                <td className="px-5 py-2 text-slate-700">{r.category}</td>
                <td className="px-5 py-2 text-right tabular-nums text-slate-500">
                  {fmt(r.avg_monthly, currency)}
                </td>
                <td className="px-5 py-2 text-right font-medium tabular-nums">
                  {fmt(r.recommended_monthly, currency)}
                </td>
                <td className="px-5 py-2 text-right tabular-nums text-slate-500">
                  {r.current_budget != null ? fmt(r.current_budget, currency) : "—"}
                </td>
                <td className="px-5 py-2 text-right">
                  <button
                    onClick={() => applyOne(r)}
                    className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                  >
                    {r.current_budget != null ? "Update" : "Set"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function SubsTab({ currency }: { currency: string }) {
  const [data, setData] = useState<SubscriptionsResponse | null>(null);
  useEffect(() => {
    setData(null);
    api.subscriptions(currency).then(setData).catch(() => setData(null));
  }, [currency]);
  if (!data) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Card label="Active subscriptions" value={String(data.active_count)} />
        <Card
          label={`Monthly burn (${currency})`}
          value={fmt(data.monthly_burn_by_currency[currency] || 0, currency)}
          tone="bad"
        />
      </div>
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-5 py-2">Merchant</th>
              <th className="px-5 py-2">Frequency</th>
              <th className="px-5 py-2 text-right">Charge</th>
              <th className="px-5 py-2 text-right">Per month</th>
              <th className="px-5 py-2">Last</th>
              <th className="px-5 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.subscriptions.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-6 text-center text-slate-400">
                  No recurring charges detected yet.
                </td>
              </tr>
            )}
            {data.subscriptions.map((s) => (
              <tr key={`${s.merchant}-${s.currency}`} className={s.active ? "" : "opacity-50"}>
                <td className="px-5 py-2 font-medium text-ink">{s.merchant}</td>
                <td className="px-5 py-2 text-slate-500">{s.frequency}</td>
                <td className="px-5 py-2 text-right tabular-nums">
                  {fmt(s.typical_amount, s.currency)}
                </td>
                <td className="px-5 py-2 text-right tabular-nums">
                  {fmt(s.monthly_cost, s.currency)}
                </td>
                <td className="px-5 py-2 text-slate-500">{s.last_charge}</td>
                <td className="px-5 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      s.active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {s.active ? "active" : "inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function RemindersTab({ currency }: { currency: string }) {
  const [items, setItems] = useState<Reminder[] | null>(null);
  useEffect(() => {
    setItems(null);
    api.reminders(currency).then(setItems).catch(() => setItems([]));
  }, [currency]);
  if (!items) return <div className="text-slate-400">Loading…</div>;

  const color = (s: string) =>
    s === "high"
      ? "border-rose-200 bg-rose-50 text-rose-700"
      : s === "medium"
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : "border-slate-200 bg-slate-50 text-slate-600";

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">
        Budget overruns, upcoming renewals, the review backlog, and tax deadlines. A daily
        email digest can be enabled via <code>reminders_cron.py</code>.
      </p>
      {items.length === 0 && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center text-emerald-700">
          ✅ Nothing needs your attention right now.
        </div>
      )}
      {items.map((r, i) => (
        <div key={i} className={`rounded-lg border px-4 py-3 text-sm ${color(r.severity)}`}>
          <span className="mr-2 font-semibold uppercase">{r.severity}</span>
          {r.message}
        </div>
      ))}
    </div>
  );
}
