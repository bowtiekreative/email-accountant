"use client";

import { useEffect, useState } from "react";
import { api, fmt, type ScheduleC } from "@/lib/api";

export default function TaxPage() {
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState<number | undefined>(undefined);
  const [data, setData] = useState<ScheduleC | null>(null);

  useEffect(() => {
    api.years().then((ys) => {
      setYears(ys);
      if (ys.length) setYear(ys[0]);
    });
  }, []);

  useEffect(() => {
    if (year) api.scheduleC(year).then(setData).catch(() => setData(null));
  }, [year]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-2xl font-bold text-ink">Tax · Schedule C</h1>
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

      {!data && <div className="text-slate-400">Loading…</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Card label="Gross income" value={fmt(data.gross_income)} tone="good" />
            <Card label="Total expenses" value={fmt(data.total_expenses)} />
            <Card
              label="Deductible"
              value={fmt(data.total_deductible)}
              tone="warn"
            />
            <Card
              label="Net profit"
              value={fmt(data.net_profit)}
              tone={data.net_profit >= 0 ? "good" : "bad"}
            />
          </div>

          <Section title="Income (Part I)" rows={data.income} showDeductible={false} />
          <Section
            title="Expenses (Part II)"
            rows={data.expenses}
            showDeductible
          />

          <p className="text-xs text-slate-400">
            Generated for {data.year}. Lines map to IRS Schedule C via each
            transaction&apos;s tax category. Review with your accountant before
            filing.
          </p>
        </>
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

function Section({
  title,
  rows,
  showDeductible,
}: {
  title: string;
  rows: { line: string; total: number; deductible: number; count: number }[];
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
            <th className="px-5 py-2">IRS line / category</th>
            <th className="px-5 py-2 text-right">Count</th>
            <th className="px-5 py-2 text-right">Total</th>
            {showDeductible && (
              <th className="px-5 py-2 text-right">Deductible</th>
            )}
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
                {fmt(r.total)}
              </td>
              {showDeductible && (
                <td className="px-5 py-2 text-right font-medium tabular-nums text-amber-700">
                  {fmt(r.deductible)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
