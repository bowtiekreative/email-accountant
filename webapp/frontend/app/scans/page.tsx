"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function ScansPage() {
  const [data, setData] = useState<{ history: any[]; current: any } | null>(
    null
  );
  const [starting, setStarting] = useState(false);

  const load = () => api.scans().then(setData).catch(() => setData(null));

  useEffect(() => {
    load();
    const t = setInterval(load, 4000); // poll while a scan may be running
    return () => clearInterval(t);
  }, []);

  async function scan() {
    setStarting(true);
    try {
      await api.startScan();
      await load();
    } finally {
      setStarting(false);
    }
  }

  const current = data?.current;
  const running = current?.status === "running";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Scans</h1>
        <button
          onClick={scan}
          disabled={starting || running}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
        >
          {running ? "Scan running…" : starting ? "Starting…" : "Scan now"}
        </button>
      </div>
      <p className="text-sm text-slate-500">
        Runs the Gmail scan + extraction + categorization pipeline, then writes
        new transactions to your ledger.
      </p>

      {current && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                running
                  ? "animate-pulse bg-amber-400"
                  : current.status === "completed"
                  ? "bg-emerald-500"
                  : "bg-rose-500"
              }`}
            />
            <span className="font-medium text-ink">
              Latest job · {current.status}
            </span>
            <span className="text-xs text-slate-400">{current.started_at}</span>
          </div>
          {current.output && (
            <pre className="mt-3 max-h-64 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
              {current.output}
            </pre>
          )}
          {current.error && (
            <pre className="mt-2 max-h-40 overflow-auto rounded bg-rose-950 p-3 text-xs text-rose-200">
              {current.error}
            </pre>
          )}
        </div>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <h2 className="border-b border-slate-100 px-5 py-3 font-semibold text-ink">
          Scan history
        </h2>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-5 py-2">Started</th>
              <th className="px-5 py-2">Type</th>
              <th className="px-5 py-2 text-right">Emails</th>
              <th className="px-5 py-2 text-right">New tx</th>
              <th className="px-5 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(data?.history?.length ?? 0) === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-slate-400">
                  No scans recorded yet.
                </td>
              </tr>
            )}
            {data?.history?.map((s) => (
              <tr key={s.id}>
                <td className="px-5 py-2 text-slate-500">{s.started_at}</td>
                <td className="px-5 py-2">{s.scan_type}</td>
                <td className="px-5 py-2 text-right tabular-nums">
                  {s.emails_processed ?? 0}
                </td>
                <td className="px-5 py-2 text-right tabular-nums">
                  {s.new_transactions ?? 0}
                </td>
                <td className="px-5 py-2">{s.scan_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
