"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  fmt,
  type CompoundResult,
  type NetWorthAccount,
  type NetWorthProjection,
  type NetWorthSummary,
  type WealthAdvice,
} from "@/lib/api";
import CurrencyPicker from "@/components/CurrencyPicker";

type Tab = "networth" | "advice" | "calculator" | "fire";
const TABS: { id: Tab; label: string }[] = [
  { id: "networth", label: "Net Worth" },
  { id: "advice", label: "Advice" },
  { id: "calculator", label: "Growth Calculator" },
  { id: "fire", label: "Financial Independence" },
];

export default function InvestPage() {
  const [tab, setTab] = useState<Tab>("advice");
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
        <div>
          <h1 className="text-2xl font-bold text-ink">Invest &amp; Build Wealth</h1>
          <p className="text-sm text-slate-500">
            Buffett-style guidance from your real numbers. Educational, not financial advice.
          </p>
        </div>
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

      {tab === "networth" && <NetWorthTab currency={currency} />}
      {tab === "advice" && <AdviceTab currency={currency} />}
      {tab === "calculator" && <CalculatorTab currency={currency} />}
      {tab === "fire" && <FireTab currency={currency} />}
    </div>
  );
}

const ASSET_CATS = [
  ["investment", "Investments / brokerage"],
  ["retirement", "Retirement (RRSP/TFSA/401k)"],
  ["savings", "Savings"],
  ["cash", "Cash / chequing"],
  ["property", "Property / real estate"],
  ["crypto", "Crypto"],
  ["other_asset", "Other asset"],
];
const LIABILITY_CATS = [
  ["credit_card", "Credit card"],
  ["loan", "Loan"],
  ["mortgage", "Mortgage"],
  ["student_loan", "Student loan"],
  ["other_debt", "Other debt"],
];

function NetWorthTab({ currency }: { currency: string }) {
  const [summary, setSummary] = useState<NetWorthSummary | null>(null);
  const [history, setHistory] = useState<{ month: string; net_worth: number }[]>([]);
  const [proj, setProj] = useState<NetWorthProjection | null>(null);
  const [rate, setRate] = useState(7);
  const [years, setYears] = useState(30);

  // add form
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"asset" | "liability">("asset");
  const [category, setCategory] = useState("investment");
  const [balance, setBalance] = useState("");

  const load = () => {
    api.nwSummary(currency).then(setSummary).catch(() => setSummary(null));
    api.nwHistory(currency).then(setHistory).catch(() => setHistory([]));
    api.nwProjection(currency, rate / 100, years).then(setProj).catch(() => setProj(null));
  };
  useEffect(load, [currency, rate, years]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name) return;
    await api.nwAddAccount({
      name,
      kind,
      category,
      currency,
      balance: balance ? Number(balance) : undefined,
    });
    setName("");
    setBalance("");
    load();
  }

  const cats = kind === "asset" ? ASSET_CATS : LIABILITY_CATS;
  const maxHist = Math.max(1, ...history.map((h) => Math.abs(h.net_worth)));

  return (
    <div className="space-y-6">
      {summary && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Assets
            </div>
            <div className="mt-2 text-2xl font-bold text-emerald-600">
              {fmt(summary.assets, currency)}
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Liabilities
            </div>
            <div className="mt-2 text-2xl font-bold text-rose-600">
              {fmt(summary.liabilities, currency)}
            </div>
          </div>
          <div className="rounded-xl border-2 border-accent bg-emerald-50 p-5 shadow-sm">
            <div className="text-xs font-medium uppercase tracking-wide text-emerald-600">
              Net worth
            </div>
            <div className="mt-2 text-2xl font-bold text-ink">
              {fmt(summary.net_worth, currency)}
            </div>
          </div>
        </div>
      )}

      {history.length > 1 && (
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 font-semibold text-ink">Net worth over time</h2>
          <div className="flex h-40 items-end gap-1">
            {history.map((h) => (
              <div
                key={h.month}
                className="flex-1 rounded-t bg-emerald-400"
                style={{ height: `${(Math.abs(h.net_worth) / maxHist) * 100}%` }}
                title={`${h.month}: ${fmt(h.net_worth, currency)}`}
              />
            ))}
          </div>
          <div className="mt-1 flex justify-between text-xs text-slate-400">
            <span>{history[0].month}</span>
            <span>{history[history.length - 1].month}</span>
          </div>
        </section>
      )}

      {proj && (
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 font-semibold text-ink">Projection</h2>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <label className="flex items-center gap-2">
              Return %/yr
              <input
                type="number"
                value={rate}
                onChange={(e) => setRate(Number(e.target.value))}
                className="w-16 rounded border border-slate-300 px-2 py-1"
              />
            </label>
            <label className="flex items-center gap-2">
              Years
              <input
                type="number"
                value={years}
                onChange={(e) => setYears(Number(e.target.value))}
                className="w-16 rounded border border-slate-300 px-2 py-1"
              />
            </label>
          </div>
          <p className="mt-3 text-sm text-slate-600">
            Starting at <strong>{fmt(proj.starting_net_worth, currency)}</strong>, investing{" "}
            <strong>{fmt(proj.monthly_surplus_invested, currency)}/mo</strong> of surplus
            at {rate}% for {years} years →
          </p>
          <p className="mt-1 text-3xl font-bold text-emerald-600">
            {fmt(proj.future_value, currency)}
          </p>
          <p className="mt-1 text-xs text-slate-400">{proj.note}</p>
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <h2 className="border-b border-slate-100 px-5 py-3 font-semibold text-ink">
          Accounts ({currency})
        </h2>
        <table className="w-full text-sm">
          <tbody className="divide-y divide-slate-100">
            {summary?.accounts.length === 0 && (
              <tr>
                <td className="px-5 py-6 text-center text-slate-400">
                  No accounts yet — add your investments, savings, and debts below.
                </td>
              </tr>
            )}
            {summary?.accounts.map((a: NetWorthAccount) => (
              <tr key={a.id}>
                <td className="px-5 py-2">
                  <span className="font-medium text-ink">{a.name}</span>
                  <span className="ml-2 text-xs text-slate-400">{a.category}</span>
                </td>
                <td
                  className={`px-5 py-2 text-right font-medium tabular-nums ${
                    a.kind === "asset" ? "text-emerald-600" : "text-rose-600"
                  }`}
                >
                  {a.kind === "liability" ? "−" : ""}
                  {fmt(a.balance, currency)}
                </td>
                <td className="px-5 py-2 text-right">
                  <button
                    onClick={() => {
                      const v = prompt(`Update balance for ${a.name}`, String(a.balance));
                      if (v !== null) api.nwSnapshot(a.id, Number(v)).then(load);
                    }}
                    className="mr-3 text-xs text-slate-500 hover:underline"
                  >
                    update
                  </button>
                  <button
                    onClick={() =>
                      confirm(`Remove ${a.name}?`) && api.nwDeleteAccount(a.id).then(load)
                    }
                    className="text-xs text-rose-600 hover:underline"
                  >
                    remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <form onSubmit={add} className="flex flex-wrap items-end gap-3 border-t border-slate-100 p-4">
          <input
            className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            placeholder="Account name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <select
            className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            value={kind}
            onChange={(e) => {
              const k = e.target.value as "asset" | "liability";
              setKind(k);
              setCategory(k === "asset" ? "investment" : "credit_card");
            }}
          >
            <option value="asset">Asset</option>
            <option value="liability">Liability</option>
          </select>
          <select
            className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {cats.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
          <input
            className="w-32 rounded border border-slate-300 px-3 py-1.5 text-sm"
            placeholder="Balance"
            type="number"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
          />
          <button
            type="submit"
            className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-600"
          >
            Add
          </button>
        </form>
      </section>
    </div>
  );
}

function Card({ label, value, tone = "default", sub }: { label: string; value: string; tone?: string; sub?: string }) {
  const cls =
    tone === "good" ? "text-emerald-600" : tone === "bad" ? "text-rose-600" : "text-ink";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${cls}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

function AdviceTab({ currency }: { currency: string }) {
  const [data, setData] = useState<WealthAdvice | null>(null);
  useEffect(() => {
    setData(null);
    api.wealthAdvice(currency).then(setData).catch(() => setData(null));
  }, [currency]);
  if (!data) return <div className="text-slate-400">Loading…</div>;

  const cf = data.cashflow;
  const sevColor = (s: string) =>
    s === "high"
      ? "border-emerald-200 bg-emerald-50"
      : s === "medium"
      ? "border-amber-200 bg-amber-50"
      : "border-slate-200 bg-slate-50";

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card label="Monthly income" value={fmt(cf.monthly_income, currency)} tone="good" />
        <Card label="Monthly spend" value={fmt(cf.monthly_expense, currency)} tone="bad" />
        <Card
          label="Monthly surplus"
          value={fmt(cf.monthly_surplus, currency)}
          tone={cf.monthly_surplus >= 0 ? "good" : "bad"}
          sub="What you could invest"
        />
        <Card
          label="Suggested to invest"
          value={fmt(data.recommended_monthly_investment, currency)}
          sub="~15% of income"
        />
      </div>

      {data.years_to_financial_independence != null && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-800">
          🎯 At your current pace, you could reach financial independence
          (a {fmt(data.fire.fire_number, currency)} portfolio) in about{" "}
          <strong>{data.years_to_financial_independence} years</strong>.
        </div>
      )}

      <div className="space-y-3">
        <h2 className="font-semibold text-ink">What to do with your money</h2>
        {data.tips.map((t, i) => (
          <div key={i} className={`rounded-xl border p-4 ${sevColor(t.severity)}`}>
            <div className="font-semibold text-ink">{t.title}</div>
            <div className="mt-1 text-sm text-slate-600">{t.body}</div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-2 font-semibold text-ink">Buffett-style principles</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
          {data.principles.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      </div>

      <p className="text-xs text-slate-400">{data.disclaimer}</p>
    </div>
  );
}

function CalculatorTab({ currency }: { currency: string }) {
  const [principal, setPrincipal] = useState(1000);
  const [monthly, setMonthly] = useState(500);
  const [rate, setRate] = useState(8);
  const [years, setYears] = useState(25);
  const [result, setResult] = useState<CompoundResult | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .compound({
          principal,
          monthly_contribution: monthly,
          annual_rate: rate / 100,
          years,
        })
        .then(setResult)
        .catch(() => setResult(null));
    }, 200);
    return () => clearTimeout(t);
  }, [principal, monthly, rate, years]);

  const maxBal = useMemo(
    () => (result ? Math.max(1, ...result.series.map((s) => s.balance)) : 1),
    [result]
  );

  const Field = ({ label, value, set, min, max, step, suffix }: any) => (
    <label className="block">
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-ink">
          {suffix === "%" ? value : fmt(value, currency)}
          {suffix === "%" ? "%" : ""}
          {suffix === "yr" ? ` (${value} yrs)` : ""}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => set(Number(e.target.value))}
        className="w-full accent-emerald-500"
      />
    </label>
  );

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <Field label="Starting amount" value={principal} set={setPrincipal} min={0} max={100000} step={500} />
        <Field label="Monthly investment" value={monthly} set={setMonthly} min={0} max={5000} step={50} />
        <Field label="Annual return" value={rate} set={setRate} min={1} max={15} step={0.5} suffix="%" />
        <Field label="Years" value={years} set={setYears} min={1} max={40} step={1} suffix="yr" />
        <p className="text-xs text-slate-400">
          8%/yr is a common long-run stock-market assumption. It is not guaranteed.
        </p>
      </div>

      <div className="space-y-4">
        {result && (
          <>
            <Card
              label={`In ${years} years you'd have`}
              value={fmt(result.future_value, currency)}
              tone="good"
              sub={`${fmt(result.total_contributed, currency)} contributed + ${fmt(
                result.total_growth,
                currency
              )} growth`}
            />
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-ink">Growth over time</h3>
              <div className="space-y-1">
                {result.series
                  .filter((_, i) => i % Math.max(1, Math.floor(result.series.length / 12)) === 0)
                  .map((s) => (
                    <div key={s.year} className="flex items-center gap-2 text-xs">
                      <span className="w-10 text-slate-400">Y{s.year}</span>
                      <div className="flex-1">
                        <div
                          className="h-3 rounded bg-emerald-400"
                          style={{ width: `${(s.balance / maxBal) * 100}%` }}
                        />
                      </div>
                      <span className="w-24 text-right tabular-nums text-slate-600">
                        {fmt(s.balance, currency)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function FireTab({ currency }: { currency: string }) {
  const [data, setData] = useState<WealthAdvice | null>(null);
  useEffect(() => {
    api.wealthAdvice(currency).then(setData).catch(() => setData(null));
  }, [currency]);
  if (!data) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <Card
          label="Your annual spending"
          value={fmt(data.fire.annual_expense, currency)}
          sub="From the last 12 months"
        />
        <Card
          label="Financial-independence number"
          value={fmt(data.fire.fire_number, currency)}
          tone="good"
          sub="At a 4% withdrawal rate"
        />
        <Card
          label="Est. years to get there"
          value={
            data.years_to_financial_independence != null
              ? `${data.years_to_financial_independence}`
              : "—"
          }
          sub="At your current saving pace"
        />
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600 shadow-sm">
        <p className="mb-2 font-semibold text-ink">What “financial independence” means</p>
        <p>{data.fire.note}</p>
        <p className="mt-2">
          The idea (the “4% rule”): once your investments are ~25× your yearly spending,
          you could live off roughly 4% of them per year without running out. Every dollar
          you cut from spending lowers this number <em>and</em> raises how much you invest —
          a double win.
        </p>
      </div>
      <p className="text-xs text-slate-400">{data.disclaimer}</p>
    </div>
  );
}
