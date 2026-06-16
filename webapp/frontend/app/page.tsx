"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, fmt, type Overview, type Reminder } from "@/lib/api";
import YearPicker from "@/components/YearPicker";
import CurrencyPicker from "@/components/CurrencyPicker";

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

function BarRow({
  name,
  total,
  max,
  currency,
}: {
  name: string;
  total: number;
  max: number;
  currency: string;
}) {
  return (
    <div className="flex items-center gap-3 py-1.5 text-sm">
      <div className="w-40 shrink-0 truncate text-slate-600">{name}</div>
      <div className="flex-1">
        <div
          className="h-5 rounded bg-emerald-100"
          style={{ width: `${max ? (total / max) * 100 : 0}%`, minWidth: "2px" }}
        />
      </div>
      <div className="w-28 shrink-0 text-right font-medium tabular-nums">
        {fmt(total, currency)}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [year, setYear] = useState<number | undefined>(undefined);
  const [currency, setCurrency] = useState<string>("");
  const [data, setData] = useState<Overview | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    api
      .overview(year, currency || undefined)
      .then((d) => {
        setData(d);
        if (!currency) setCurrency(d.active_currency);
      })
      .catch((e) => setError(String(e)));
  }, [year, currency]);

  useEffect(() => {
    api.reminders().then(setReminders).catch(() => setReminders([]));
  }, []);

  const active = currency || data?.active_currency || "USD";
  const totals = data?.totals_by_currency[active];
  const others =
    data?.currencies.filter((c) => c !== active) ?? [];

  const maxMonth = data
    ? Math.max(1, ...data.monthly_trend.map((m) => Math.max(m.income, m.expense)))
    : 1;
  const maxCat = data ? Math.max(1, ...data.by_category.map((c) => c.total)) : 1;
  const maxMerch = data ? Math.max(1, ...data.by_merchant.map((c) => c.total)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
        <div className="flex items-center gap-3">
          {data && (
            <CurrencyPicker
              currencies={data.currencies}
              value={active}
              onChange={setCurrency}
            />
          )}
          <YearPicker value={year} onChange={setYear} />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Could not reach the API at <code>{api.base}</code>. Is the backend
          running? ({error})
        </div>
      )}

      {reminders.length > 0 && (
        <div className="space-y-2">
          {reminders.slice(0, 3).map((r, i) => (
            <Link
              key={i}
              href="/planning"
              className={`block rounded-lg border px-4 py-2 text-sm transition hover:opacity-90 ${
                r.severity === "high"
                  ? "border-rose-200 bg-rose-50 text-rose-700"
                  : r.severity === "medium"
                  ? "border-amber-200 bg-amber-50 text-amber-800"
                  : "border-slate-200 bg-slate-50 text-slate-600"
              }`}
            >
              🔔 {r.message}
            </Link>
          ))}
          {reminders.length > 3 && (
            <Link href="/planning" className="text-xs text-slate-400 hover:text-ink">
              +{reminders.length - 3} more in Planning → Reminders
            </Link>
          )}
        </div>
      )}

      {!data && !error && <div className="text-slate-400">Loading…</div>}

      {data && totals && (
        <>
          <p className="text-sm text-slate-500">
            Showing <strong>{active}</strong> only. CAD and USD are tracked
            separately and never added together.
          </p>

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label={`Income (${active})`} value={fmt(totals.income, active)} tone="good" />
            <Stat label={`Expenses (${active})`} value={fmt(totals.expense, active)} tone="bad" />
            <Stat
              label={`Net (${active})`}
              value={fmt(totals.net, active)}
              tone={totals.net >= 0 ? "good" : "bad"}
            />
            <Stat label={`Deductible (${active})`} value={fmt(totals.deductible, active)} />
          </div>

          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500">
            <span>{totals.transaction_count} transactions</span>
            {others.map((c) => {
              const t = data.totals_by_currency[c];
              return (
                <span key={c} className="text-slate-400">
                  {c}: net {fmt(t.net, c)} ({t.transaction_count} txns)
                </span>
              );
            })}
            {data.needs_review > 0 && (
              <Link
                href="/review"
                className="rounded-full bg-amber-100 px-3 py-1 font-medium text-amber-700 hover:bg-amber-200"
              >
                {data.needs_review} need review →
              </Link>
            )}
          </div>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 font-semibold text-ink">
              Monthly trend ({active})
            </h2>
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
                      title={`Income ${fmt(m.income, active)}`}
                    />
                    <div
                      className="h-3 rounded bg-rose-400"
                      style={{ width: `${(m.expense / maxMonth) * 50}%` }}
                      title={`Expense ${fmt(m.expense, active)}`}
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
                Top expense categories ({active})
              </h2>
              {data.by_category.map((c) => (
                <BarRow
                  key={c.name}
                  name={c.name}
                  total={c.total}
                  max={maxCat}
                  currency={active}
                />
              ))}
            </section>
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 font-semibold text-ink">
                Top merchants ({active})
              </h2>
              {data.by_merchant.map((c) => (
                <BarRow
                  key={c.name}
                  name={c.name}
                  total={c.total}
                  max={maxMerch}
                  currency={active}
                />
              ))}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
