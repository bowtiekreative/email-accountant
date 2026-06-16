"use client";

import { useEffect, useState } from "react";
import { api, fmt, type GstHst, type TaxReport } from "@/lib/api";

type Tab = "t2125" | "schedulec" | "gst";

const TABS: { id: Tab; label: string }[] = [
  { id: "t2125", label: "🇨🇦 CRA T2125" },
  { id: "schedulec", label: "🇺🇸 US Schedule C" },
  { id: "gst", label: "GST / HST" },
];

export default function TaxPage() {
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState<number | undefined>(undefined);
  const [tab, setTab] = useState<Tab>("t2125");

  useEffect(() => {
    api.years().then((ys) => {
      setYears(ys);
      if (ys.length) setYear(ys[0]);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-2xl font-bold text-ink">Tax</h1>
        <div className="flex items-center gap-3">
          <select
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
            value={year ?? ""}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
          <button
            onClick={() => window.print()}
            className="rounded-md bg-ink px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
          >
            Print / Export PDF
          </button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-slate-200 print:hidden">
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

      {year && tab === "t2125" && (
        <FormView
          key={`t2125-${year}`}
          load={() => api.t2125(year)}
          intro="Canadian sole-proprietor business income (Form T2125), in CAD. Expense lines map to CRA Part 4 line numbers."
        />
      )}
      {year && tab === "schedulec" && (
        <FormView
          key={`schedc-${year}`}
          load={() => api.scheduleC(year)}
          intro="US Schedule C view, in USD — useful for your US-sourced business activity."
        />
      )}
      {year && tab === "gst" && (
        <GstView key={`gst-${year}`} load={() => api.gstHst(year)} />
      )}
    </div>
  );
}

function Card({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "good" | "bad" | "warn";
}) {
  const cls = {
    default: "text-ink",
    good: "text-emerald-600",
    bad: "text-rose-600",
    warn: "text-amber-600",
  }[tone];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div className={`mt-2 text-2xl font-bold ${cls}`}>{value}</div>
    </div>
  );
}

function FormView({
  load,
  intro,
}: {
  load: () => Promise<TaxReport>;
  intro: string;
}) {
  const [data, setData] = useState<TaxReport | null>(null);
  useEffect(() => {
    setData(null);
    load().then(setData).catch(() => setData(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!data) return <div className="text-slate-400">Loading…</div>;
  const cur = data.currency;
  return (
    <>
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
        {data.form} · {data.year} · amounts in {cur}. {intro}
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card label="Gross income" value={fmt(data.gross_income, cur)} tone="good" />
        <Card label="Total expenses" value={fmt(data.total_expenses, cur)} />
        <Card label="Deductible" value={fmt(data.total_deductible, cur)} tone="warn" />
        <Card
          label="Net profit"
          value={fmt(data.net_profit, cur)}
          tone={data.net_profit >= 0 ? "good" : "bad"}
        />
      </div>
      <Section title="Income" rows={data.income} currency={cur} showDeductible={false} />
      <Section title="Expenses" rows={data.expenses} currency={cur} showDeductible />
      <p className="text-xs text-slate-400">
        Lines are mapped automatically from each transaction&apos;s category.
        Review with your accountant before filing.
      </p>
    </>
  );
}

function GstView({ load }: { load: () => Promise<GstHst> }) {
  const [data, setData] = useState<GstHst | null>(null);
  useEffect(() => {
    setData(null);
    load().then(setData).catch(() => setData(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!data) return <div className="text-slate-400">Loading…</div>;
  const cur = data.currency;
  return (
    <>
      <div className="grid grid-cols-2 gap-4">
        <Card label="Taxable sales (CAD)" value={fmt(data.taxable_sales, cur)} tone="good" />
        <Card label="Eligible expenses (CAD)" value={fmt(data.eligible_expenses, cur)} />
      </div>
      <div className="flex gap-6 text-sm text-slate-500">
        <span>{data.sales_count} sales</span>
        <span>{data.expense_count} expenses</span>
      </div>
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        {data.note}
      </div>
    </>
  );
}

function Section({
  title,
  rows,
  currency,
  showDeductible,
}: {
  title: string;
  rows: { line: string; total: number; deductible: number; count: number }[];
  currency: string;
  showDeductible: boolean;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <h2 className="border-b border-slate-100 px-5 py-3 font-semibold text-ink">
        {title}
      </h2>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-5 py-2">Line / category</th>
            <th className="px-5 py-2 text-right">Count</th>
            <th className="px-5 py-2 text-right">Total</th>
            {showDeductible && <th className="px-5 py-2 text-right">Deductible</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length === 0 && (
            <tr>
              <td colSpan={4} className="px-5 py-6 text-center text-slate-400">
                None.
              </td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.line}>
              <td className="px-5 py-2 text-slate-700">{r.line}</td>
              <td className="px-5 py-2 text-right tabular-nums text-slate-500">
                {r.count}
              </td>
              <td className="px-5 py-2 text-right tabular-nums">
                {fmt(r.total, currency)}
              </td>
              {showDeductible && (
                <td className="px-5 py-2 text-right font-medium tabular-nums text-amber-700">
                  {fmt(r.deductible, currency)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
