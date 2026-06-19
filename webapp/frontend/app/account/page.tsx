"use client";

import { useEffect, useState } from "react";
import { api, clearCache } from "@/lib/api";

export default function AccountPage() {
  const [username, setUsername] = useState("");
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.me().then((m) => setUsername(m.username)).catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg("");
    setErr("");
    if (newPw.length < 8) {
      setErr("New password must be at least 8 characters.");
      return;
    }
    if (newPw !== confirm) {
      setErr("New passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(oldPw, newPw);
      setMsg("Password changed.");
      setOldPw("");
      setNewPw("");
      setConfirm("");
    } catch (e: any) {
      setErr(e.message || "Could not change password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <h1 className="text-2xl font-bold text-ink">Account</h1>
      <p className="text-sm text-slate-500">
        Signed in as <strong>{username || "…"}</strong>.
      </p>

      <form
        onSubmit={submit}
        className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h2 className="font-semibold text-ink">Change password</h2>
        <input
          type="password"
          placeholder="Current password"
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
          value={oldPw}
          onChange={(e) => setOldPw(e.target.value)}
        />
        <input
          type="password"
          placeholder="New password (min 8 characters)"
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
          value={newPw}
          onChange={(e) => setNewPw(e.target.value)}
        />
        <input
          type="password"
          placeholder="Confirm new password"
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        {err && <p className="text-sm text-rose-600">{err}</p>}
        {msg && <p className="text-sm text-emerald-600">{msg}</p>}
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {busy ? "Saving…" : "Change password"}
        </button>
      </form>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold text-ink">Maintenance</h2>
        <p className="mt-1 text-sm text-slate-500">
          Clear locally cached data and reload (you stay signed in).
        </p>
        <button
          onClick={() => clearCache()}
          className="mt-3 rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50"
        >
          Clear cache
        </button>
      </div>
    </div>
  );
}
