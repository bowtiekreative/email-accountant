"use client";

import { useEffect, useState } from "react";
import { api, type EmailAccount } from "@/lib/api";

const PROVIDERS = [
  { id: "gmail", label: "Gmail" },
  { id: "outlook", label: "Outlook / Office365" },
  { id: "yahoo", label: "Yahoo" },
  { id: "icloud", label: "iCloud" },
  { id: "imap", label: "Other IMAP" },
];

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<EmailAccount[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  // form
  const [label, setLabel] = useState("");
  const [email, setEmail] = useState("");
  const [provider, setProvider] = useState("gmail");
  const [password, setPassword] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("993");

  const load = () => api.accounts().then(setAccounts).catch(() => setAccounts([]));
  useEffect(() => {
    load();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setAdding(true);
    try {
      await api.addAccount({
        label,
        email,
        provider,
        password: password || undefined,
        imap_host: provider === "imap" ? host : undefined,
        imap_port: provider === "imap" ? Number(port) : undefined,
      });
      setLabel("");
      setEmail("");
      setPassword("");
      setHost("");
      await load();
    } catch (err: any) {
      setError(String(err.message || err));
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Email accounts</h1>
      <p className="text-sm text-slate-500">
        Add the inboxes to scan for receipts — Gmail or any IMAP provider. Each
        account needs an <strong>app password</strong> (not your login
        password). Credentials are stored locally in{" "}
        <code>~/.email-accountant/accounts.json</code> and never leave your
        machine.
      </p>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-5 py-2">Label</th>
              <th className="px-5 py-2">Email</th>
              <th className="px-5 py-2">Provider</th>
              <th className="px-5 py-2">Password</th>
              <th className="px-5 py-2">Active</th>
              <th className="px-5 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {accounts === null && (
              <tr>
                <td colSpan={6} className="px-5 py-6 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {accounts?.map((a) => (
              <tr key={a.label} className={a.active ? "" : "opacity-50"}>
                <td className="px-5 py-2 font-medium text-ink">{a.label}</td>
                <td className="px-5 py-2 text-slate-600">{a.email}</td>
                <td className="px-5 py-2 text-slate-500">{a.provider}</td>
                <td className="px-5 py-2">
                  {a.has_password ? (
                    <span className="text-emerald-600">✓ set</span>
                  ) : (
                    <span className="text-rose-600">✗ missing</span>
                  )}
                </td>
                <td className="px-5 py-2">
                  <button
                    onClick={() => api.toggleAccount(a.label, !a.active).then(load)}
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      a.active
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {a.active ? "on" : "off"}
                  </button>
                </td>
                <td className="px-5 py-2 text-right">
                  <button
                    onClick={() =>
                      confirm(`Remove ${a.label}?`) &&
                      api.deleteAccount(a.label).then(load)
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
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 font-semibold text-ink">Add an account</h2>
        <form onSubmit={add} className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
              Label (a nickname)
            </span>
            <input
              required
              className="w-full rounded border border-slate-300 px-3 py-1.5"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="personal"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
              Email address
            </span>
            <input
              required
              type="email"
              className="w-full rounded border border-slate-300 px-3 py-1.5"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
              Provider
            </span>
            <select
              className="w-full rounded border border-slate-300 px-3 py-1.5"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
              App password
            </span>
            <input
              type="password"
              className="w-full rounded border border-slate-300 px-3 py-1.5"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="16-character app password"
            />
          </label>
          {provider === "imap" && (
            <>
              <label className="text-sm">
                <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
                  IMAP host
                </span>
                <input
                  className="w-full rounded border border-slate-300 px-3 py-1.5"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  placeholder="imap.example.com"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
                  IMAP port
                </span>
                <input
                  className="w-full rounded border border-slate-300 px-3 py-1.5"
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                />
              </label>
            </>
          )}
          <div className="md:col-span-2">
            {error && <p className="mb-2 text-sm text-rose-600">{error}</p>}
            <button
              type="submit"
              disabled={adding}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              {adding ? "Adding…" : "Add account"}
            </button>
          </div>
        </form>
        <p className="mt-3 text-xs text-slate-400">
          After adding, run a scan from the <strong>Scans</strong> tab to pull in
          that inbox.
        </p>
      </section>
    </div>
  );
}
