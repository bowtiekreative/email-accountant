"use client";

import { useEffect, useState } from "react";
import { api, fmt, type Transaction } from "@/lib/api";
import YearPicker from "@/components/YearPicker";

const badge = (text?: string) => {
  const map: Record<string, string> = {
    business: "bg-indigo-100 text-indigo-700",
    personal: "bg-sky-100 text-sky-700",
    unknown: "bg-slate-100 text-slate-500",
    income: "bg-emerald-100 text-emerald-700",
    expense: "bg-rose-100 text-rose-700",
  };
  return map[text || ""] || "bg-slate-100 text-slate-600";
};

export default function TransactionsPage() {
  const [year, setYear] = useState<number | undefined>(undefined);
  const [domain, setDomain] = useState("");
  const [type, setType] = useState("");
  const [currency, setCurrency] = useState("");
  const [currencies, setCurrencies] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Transaction[] | null>(null);

  useEffect(() => {
    api.currencies().then(setCurrencies).catch(() => setCurrencies([]));
  }, []);

  useEffect(() => {
    setRows(null);
    const t = setTimeout(() => {
      api
        .transactions({ year, domain, type, currency, q, limit: 500 })
        .then(setRows)
        .catch(() => setRows([]));
    }, 200);
    return () => clearTimeout(t);
  }, [year, domain, type, currency, q]);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-ink">Transactions</h1>

      <div className="flex flex-wrap items-center gap-3">
        <YearPicker value={year} onChange={setYear} />
        <select
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
        >
          <option value="">All domains</option>
          <option value="business">Business</option>
          <option value="personal">Personal</option>
          <option value="unknown">Unknown</option>
        </select>
        <select
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
          value={type}
          onChange={(e) => setType(e.target.value)}
        >
          <option value="">Income & expense</option>
          <option value="income">Income</option>
          <option value="expense">Expense</option>
        </select>
        {currencies.length > 1 && (
          <select
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
          >
            <option value="">All currencies</option>
            {currencies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
        <input
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
          placeholder="Search merchant or subject…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Merchant</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Domain</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Cur</th>
              <th className="px-4 py-3 text-right">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows === null && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {rows?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  No transactions found.
                </td>
              </tr>
            )}
            {rows?.map((t) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                  {(t.email_date || "").slice(0, 10)}
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-ink">
                    {t.merchant_name || "—"}
                  </div>
                  <div className="max-w-xs truncate text-xs text-slate-400">
                    {t.email_subject}
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-600">{t.category || "—"}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${badge(t.domain)}`}>
                    {t.domain}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${badge(t.transaction_type)}`}>
                    {t.transaction_type}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-500">
                    {t.currency}
                  </span>
                </td>
                <td
                  className={`whitespace-nowrap px-4 py-3 text-right font-medium tabular-nums ${
                    t.transaction_type === "income"
                      ? "text-emerald-600"
                      : "text-slate-800"
                  }`}
                >
                  {fmt(t.amount, t.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows && <p className="text-xs text-slate-400">{rows.length} shown</p>}
    </div>
  );
}
