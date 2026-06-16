"use client";

import { useEffect, useState } from "react";
import {
  api,
  fmt,
  type Category,
  type Transaction,
  type TransactionPatch,
} from "@/lib/api";

export default function ReviewPage() {
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [saving, setSaving] = useState<string | null>(null);

  const load = () => {
    api
      .transactions({ needs_review: true, limit: 500 })
      .then(setRows)
      .catch(() => setRows([]));
  };

  useEffect(() => {
    load();
    api.categories().then(setCats).catch(() => setCats([]));
  }, []);

  async function patch(id: string, changes: TransactionPatch) {
    setSaving(id);
    try {
      await api.updateTransaction(id, changes);
    } finally {
      setSaving(null);
    }
  }

  async function approve(t: Transaction) {
    await patch(t.id, { reviewed: true, needs_review: false });
    setRows((r) => r?.filter((x) => x.id !== t.id) ?? null);
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Review queue</h1>
        <button
          onClick={load}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>
      <p className="text-sm text-slate-500">
        Low-confidence or unknown transactions. Fix the classification, then
        approve to clear it from the queue.
      </p>

      {rows === null && <div className="text-slate-400">Loading…</div>}
      {rows?.length === 0 && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center text-emerald-700">
          🎉 Nothing to review — your ledger is clean.
        </div>
      )}

      <div className="space-y-3">
        {rows?.map((t) => (
          <div
            key={t.id}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-semibold text-ink">
                  {t.merchant_name || "Unknown merchant"} ·{" "}
                  <span className="tabular-nums">
                    {fmt(t.amount, t.currency)}
                  </span>
                  <span className="ml-1 text-xs text-slate-400">
                    {t.currency}
                  </span>
                </div>
                <div className="text-xs text-slate-400">
                  {(t.email_date || "").slice(0, 10)} · {t.email_subject}
                </div>
                <div className="mt-1 text-xs text-amber-600">
                  confidence{" "}
                  {Math.round((t.classification_confidence || 0) * 100)}% ·{" "}
                  {t.classification_method}
                </div>
              </div>
              <button
                onClick={() => approve(t)}
                disabled={saving === t.id}
                className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                {saving === t.id ? "Saving…" : "Approve"}
              </button>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Field label="Domain">
                <select
                  className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                  defaultValue={t.domain}
                  onChange={(e) => patch(t.id, { domain: e.target.value })}
                >
                  <option value="business">Business</option>
                  <option value="personal">Personal</option>
                  <option value="unknown">Unknown</option>
                </select>
              </Field>
              <Field label="Type">
                <select
                  className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                  defaultValue={t.transaction_type}
                  onChange={(e) =>
                    patch(t.id, { transaction_type: e.target.value })
                  }
                >
                  <option value="expense">Expense</option>
                  <option value="income">Income</option>
                  <option value="transfer">Transfer</option>
                  <option value="unknown">Unknown</option>
                </select>
              </Field>
              <Field label="Category">
                <select
                  className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                  defaultValue={t.category || ""}
                  onChange={(e) => patch(t.id, { category: e.target.value })}
                >
                  <option value="">—</option>
                  {cats.map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Deductible">
                <label className="flex items-center gap-2 py-1 text-sm">
                  <input
                    type="checkbox"
                    defaultChecked={!!t.is_deductible}
                    onChange={(e) =>
                      patch(t.id, { is_deductible: e.target.checked })
                    }
                  />
                  Tax deductible
                </label>
              </Field>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
      {children}
    </div>
  );
}
