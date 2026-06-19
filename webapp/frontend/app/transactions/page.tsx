"use client";

import { useEffect, useState } from "react";
import { api, fmt, type Transaction, type TransactionDetail } from "@/lib/api";
import YearPicker from "@/components/YearPicker";

const PAGE_SIZE = 100;

const fmtDate = (s?: string) => {
  if (!s) return "—";
  // Try parsing RFC2822 format like "Wed, 17 Jun 2026 23:04:02"
  const d = new Date(s);
  if (isNaN(d.getTime())) return s.slice(0, 16);
  return d.toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "2-digit" });
};

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

const stateBadge = (s?: string) => {
  const map: Record<string, string> = {
    paid: "bg-emerald-100 text-emerald-700",
    failed: "bg-rose-100 text-rose-700",
    declined: "bg-rose-100 text-rose-700",
    refund: "bg-amber-100 text-amber-800",
    pending: "bg-slate-100 text-slate-600",
    scam: "bg-rose-200 text-rose-900",
  };
  return map[s || "paid"] || "bg-slate-100 text-slate-600";
};

export default function TransactionsPage() {
  const [year, setYear] = useState<number | undefined>(undefined);
  const [domain, setDomain] = useState("");
  const [type, setType] = useState("");
  const [state, setState] = useState("");
  const [currency, setCurrency] = useState("");
  const [currencies, setCurrencies] = useState<string[]>([]);
  const [account, setAccount] = useState("");
  const [accounts, setAccounts] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);

  useEffect(() => {
    api.currencies().then(setCurrencies).catch(() => setCurrencies([]));
    api.accountList().then(setAccounts).catch(() => setAccounts([]));
  }, []);

  const filters = { year, domain, type, currency, account, state, q };

  function load() {
    setRows(null);
    setSelected(new Set());
    api
      .transactions({ ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then(setRows)
      .catch(() => setRows([]));
    api.transactionsCount(filters).then((r) => setTotal(r.total)).catch(() => setTotal(0));
  }

  // Reload on filter/page change (debounced for search).
  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, domain, type, currency, account, state, q, page]);

  // Reset to page 0 when filters change.
  useEffect(() => {
    setPage(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, domain, type, currency, account, state, q]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const allOnPage = rows && rows.length > 0 && rows.every((r) => selected.has(r.id));

  function toggle(id: string) {
    const s = new Set(selected);
    s.has(id) ? s.delete(id) : s.add(id);
    setSelected(s);
  }
  function toggleAll() {
    if (!rows) return;
    setSelected(allOnPage ? new Set() : new Set(rows.map((r) => r.id)));
  }

  async function deleteSelected() {
    if (selected.size === 0) return;
    if (!confirm(`Delete ${selected.size} selected transaction(s)?`)) return;
    setBusy("delete");
    try {
      await api.deleteTransactions([...selected]);
      load();
    } finally {
      setBusy("");
    }
  }
  async function clearAll() {
    if (!confirm("Delete ALL transactions and emails and start over? This cannot be undone.")) return;
    if (!confirm("Are you absolutely sure? Everything will be wiped.")) return;
    setBusy("clear");
    try {
      await api.clearTransactions();
      setPage(0);
      load();
    } finally {
      setBusy("");
    }
  }
  async function reprocess() {
    setBusy("reprocess");
    try {
      const r = await api.reprocess();
      alert(`Reprocessed ${r.updated} of ${r.scanned} transactions.`);
      load();
    } finally {
      setBusy("");
    }
  }

  const select = "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-ink">Transactions</h1>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={reprocess}
            disabled={!!busy}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
          >
            {busy === "reprocess" ? "Reprocessing…" : "Reprocess all"}
          </button>
          <button
            onClick={deleteSelected}
            disabled={selected.size === 0 || !!busy}
            className="rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-40"
          >
            Delete selected ({selected.size})
          </button>
          <button
            onClick={clearAll}
            disabled={!!busy}
            className="rounded-md border border-rose-300 px-3 py-1.5 text-sm text-rose-700 hover:bg-rose-50 disabled:opacity-50"
          >
            {busy === "clear" ? "Clearing…" : "Clear all"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <YearPicker value={year} onChange={setYear} />
        <select className={select} value={domain} onChange={(e) => setDomain(e.target.value)}>
          <option value="">All domains</option>
          <option value="business">Business</option>
          <option value="personal">Personal</option>
          <option value="unknown">Unknown</option>
        </select>
        <select className={select} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">Income & expense</option>
          <option value="income">Income</option>
          <option value="expense">Expense</option>
        </select>
        <select className={select} value={state} onChange={(e) => setState(e.target.value)}>
          <option value="">Any state</option>
          <option value="paid">Paid</option>
          <option value="failed">Failed</option>
          <option value="declined">Declined</option>
          <option value="refund">Refund</option>
          <option value="pending">Pending</option>
          <option value="scam">Scam</option>
        </select>
        {currencies.length > 1 && (
          <select className={select} value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option value="">All currencies</option>
            {currencies.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        )}
        {accounts.length > 1 && (
          <select className={select} value={account} onChange={(e) => setAccount(e.target.value)}>
            <option value="">All accounts</option>
            {accounts.map((a) => (
              <option key={a} value={a}>{a}</option>
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
              <th className="px-3 py-3">
                <input type="checkbox" checked={!!allOnPage} onChange={toggleAll} />
              </th>
              <th className="px-3 py-3">Date</th>
              <th className="px-3 py-3">Merchant</th>
              <th className="px-3 py-3">Category</th>
              <th className="px-3 py-3">State</th>
              <th className="px-3 py-3">Domain</th>
              <th className="px-3 py-3">Cur</th>
              <th className="px-3 py-3 text-right">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows === null && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Loading…</td></tr>
            )}
            {rows?.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">No transactions.</td></tr>
            )}
            {rows?.map((t) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={selected.has(t.id)} onChange={() => toggle(t.id)} />
                </td>
                <td className="cursor-pointer whitespace-nowrap px-3 py-2 text-slate-500" onClick={() => setDetailId(t.id)}>
                  {fmtDate(t.email_date)}
                </td>
                <td className="cursor-pointer px-3 py-2" onClick={() => setDetailId(t.id)}>
                  <div className="font-medium text-ink">{t.merchant_name || "—"}</div>
                  <div className="max-w-xs truncate text-xs text-slate-400">{t.email_subject}</div>
                </td>
                <td className="cursor-pointer px-3 py-2 text-slate-600" onClick={() => setDetailId(t.id)}>{t.category || "—"}</td>
                <td className="px-3 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${stateBadge(t.txn_state)}`}>
                    {t.txn_state || "paid"}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${badge(t.domain)}`}>{t.domain}</span>
                </td>
                <td className="px-3 py-2 text-xs text-slate-500">{t.currency}</td>
                <td className={`whitespace-nowrap px-3 py-2 text-right font-medium tabular-nums ${t.transaction_type === "income" ? "text-emerald-600" : "text-slate-800"}`}>
                  {fmt(t.amount, t.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>{total.toLocaleString()} transactions</span>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-50 disabled:opacity-40"
          >
            ← Prev
          </button>
          <span>Page {page + 1} of {pages}</span>
          <button
            onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
            disabled={page >= pages - 1}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-50 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      </div>

      {detailId && <DetailModal id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

function DetailModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [data, setData] = useState<TransactionDetail | null>(null);
  useEffect(() => {
    api.transactionDetail(id).then(setData).catch(() => setData(null));
  }, [id]);

  const t = data?.transaction;
  const email = data?.email;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-black/40 p-4" onClick={onClose}>
      <div className="my-8 w-full max-w-3xl rounded-xl bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-ink">Transaction detail</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-ink">✕</button>
        </div>
        {!data && <div className="p-6 text-slate-400">Loading…</div>}
        {t && (
          <div className="space-y-4 p-5">
            <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
              <Field label="Merchant" value={t.merchant_name} />
              <Field label="Amount" value={fmt(t.amount, t.currency)} />
              <Field label="State" value={t.txn_state || "paid"} />
              <Field label="Date" value={(t.email_date || "").slice(0, 10)} />
              <Field label="Domain" value={t.domain} />
              <Field label="Type" value={t.transaction_type} />
              <Field label="Category" value={t.category} />
              <Field label="Tax line" value={t.tax_category} />
              <Field label="Account" value={t.account} />
            </div>
            <div>
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Email subject</div>
              <div className="text-sm text-slate-700">{t.email_subject || "—"}</div>
            </div>
            {data.attachments.length > 0 && (
              <div>
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                  Attachments ({data.attachments.length})
                </div>
                <ul className="list-inside list-disc text-sm text-slate-600">
                  {data.attachments.map((a, i) => (
                    <li key={i}>{a.filename} <span className="text-slate-400">{a.mime_type}</span></li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Email preview</div>
              {(() => {
                const html = email?.body_html || (email?.body_plain && email.body_plain.trim().toLowerCase().startsWith('<') ? email.body_plain : '');
                if (html) {
                  return (
                    <iframe
                      title="email"
                      sandbox=""
                      className="h-96 w-full rounded border border-slate-200 bg-white"
                      srcDoc={html}
                    />
                  );
                }
                return (
                  <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                    {email?.body_plain || email?.snippet || t.receipt_ocr_text || "No email body stored."}
                  </pre>
                );
              })()}
            </div>
            {/* Line items */}
            {(() => {
              try {
                const items = typeof t.line_items === 'string' ? JSON.parse(t.line_items) : t.line_items;
                if (Array.isArray(items) && items.length > 0) {
                  return (
                    <div>
                      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Line items</div>
                      <table className="w-full text-sm">
                        <tbody>
                          {items.map((li: any, i: number) => (
                            <tr key={i} className="border-b border-slate-100">
                              <td className="py-1.5 text-slate-700">{li.description || li.name || '—'}</td>
                              {li.quantity && <td className="py-1.5 text-right text-slate-500">x{li.quantity}</td>}
                              <td className="py-1.5 text-right font-medium text-slate-800">{fmt(li.amount || li.price || 0, t.currency)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                }
              } catch { /* line_items not parseable */ }
              return null;
            })()}
            {/* Classification details */}
            <div className="grid grid-cols-2 gap-3 text-sm border-t border-slate-100 pt-3">
              <Field label="Confidence" value={t.classification_confidence ? `${(t.classification_confidence * 100).toFixed(0)}%` : '—'} />
              <Field label="Method" value={t.classification_method || '—'} />
              <Field label="Deductible" value={t.is_deductible ? `Yes (${(t.deduction_rate * 100).toFixed(0)}%)` : 'No'} />
              <Field label="Recurring" value={t.is_recurring ? `Yes (${t.recurring_frequency || '—'})` : 'No'} />
              <Field label="Reviewed" value={t.reviewed ? 'Yes' : 'No'} />
              <Field label="Flagged" value={t.flagged ? `Yes: ${t.flag_reason || ''}` : 'No'} />
            </div>
            {/* Email metadata */}
            <div className="grid grid-cols-2 gap-3 text-sm border-t border-slate-100 pt-3">
              <Field label="From" value={email?.from_email || t.email_from} />
              <Field label="To" value={email?.to_header || '—'} />
              <Field label="Message ID" value={email?.message_id || '—'} />
              <Field label="SPF" value={email?.spf_status ? 'pass' : '—'} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: any }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-slate-800">{value ?? "—"}</div>
    </div>
  );
}
