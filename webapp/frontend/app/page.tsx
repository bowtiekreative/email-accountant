"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, fmt, type Overview } from "@/lib/api";
import YearPicker from "@/components/YearPicker";

function Stat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "good" | "bad" | "warn";
}) {
  const toneCls = {
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
      <div className={`mt-2 text-2xl font-bold ${toneCls}`}>{value}</div>
    </div>
  );
}

function BarRow({ name, total, max }: { name: string; total: number; max: number }) {
  return (
    <div className="flex items-center gap-3 py-1.5 text-sm">
      <div className="w-40 shrink-0 truncate text-slate-600">{name}</div>
      <div className="flex-1">
        <div
          className="h-5 rounded bg-emerald-100"
          style={{ width: `${max ? (total / max) * 100 : 0}%`, minWidth: "2px" }}
        />
      </div>
      <div className="w-24 shrink-0 text-right font-medium tabular-nums">
        {fmt(total)}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [year, setYear] = useState<number | undefined>(undefined);
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    api
      .overview(year)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [year]);

  const maxMonth = data
    ? Math.max(1, ...data.monthly_trend.map((m) => Math.max(m.income, m.expense)))
    : 1;
  const maxCat = data ? Math.max(1, ...data.by_category.map((c) => c.total)) : 1;
  const maxMerch = data ? Math.max(1, ...data.by_merchant.map((c) => c.total)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
        <YearPicker value={year} onChange={setYear} />
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Could not reach the API at <code>{api.base}</code>. Is the backend
          running? ({error})
        </div>
      )}

      {!data && !error && <div className="text-slate-400">Loading…</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Income" value={fmt(data.totals.income)} tone="good" />
            <Stat label="Expenses" value={fmt(data.totals.expense)} tone="bad" />
            <Stat
              label="Net"
              value={fmt(data.totals.net)}
              tone={data.totals.net >= 0 ? "good" : "bad"}
            />
            <Stat
              label="Deductible"
              value={fmt(data.totals.deductible)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500">
            <span>{data.totals.transaction_count} transactions</span>
            {data.totals.needs_review > 0 && (
              <Link
                href="/review"
                className="rounded-full bg-amber-100 px-3 py-1 font-medium text-amber-700 hover:bg-amber-200"
              >
                {data.totals.needs_review} need review →
              </Link>
            )}
          </div>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 font-semibold text-ink">Monthly trend</h2>
            <div className="space-y-2">
              {data.monthly_trend.length === 0 && (
                <p className="text-sm text-slate-400">No data yet.</p>
              )}
              {data.monthly_trend.map((m) => (
                <div key={m.month} className="text-sm">
                  <div className="mb-0.5 text-xs text-slate-400">{m.month}</div>
                  <div className="flex items-center gap-2">
                    <div
                      className="h-3 rounded bg-emerald-400"
                      style={{ width: `${(m.income / maxMonth) * 50}%` }}
                      title={`Income ${fmt(m.income)}`}
                    />
                    <div
                      className="h-3 rounded bg-rose-400"
                      style={{ width: `${(m.expense / maxMonth) * 50}%` }}
                      title={`Expense ${fmt(m.expense)}`}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded bg-emerald-400" />
                Income
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded bg-rose-400" />
                Expense
              </span>
            </div>
          </section>

          <div className="grid gap-6 md:grid-cols-2">
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 font-semibold text-ink">
                Top expense categories
              </h2>
              {data.by_category.map((c) => (
                <BarRow key={c.name} name={c.name} total={c.total} max={maxCat} />
              ))}
            </section>
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 font-semibold text-ink">Top merchants</h2>
              {data.by_merchant.map((c) => (
                <BarRow key={c.name} name={c.name} total={c.total} max={maxMerch} />
              ))}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
