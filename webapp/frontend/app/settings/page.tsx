"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  api,
  type EmailAccount,
  type StackConfig,
} from "@/lib/api";
import { supabaseConfigured } from "@/lib/supabase";
import { PageHeader } from "@/components/PageHeader";
import {
  Button,
  Card,
  Icon,
  PageState,
  SectionTitle,
  StatusPill,
} from "@/lib/ui";

const inputCls =
  "w-full rounded-md border border-line-strong bg-surface px-3.5 py-2.5 font-body text-sm text-ink-900 outline-none transition-colors placeholder:text-ink-400 focus:border-violet-500";
const labelCls = "text-[12.5px] font-semibold text-ink-700";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-1 flex-col gap-1.5">
      <span className={labelCls}>{label}</span>
      {children}
    </label>
  );
}

function Note({ tone, children }: { tone: "success" | "error"; children: React.ReactNode }) {
  return (
    <p
      className="text-[13px] font-medium"
      style={{ color: tone === "success" ? "var(--success-600)" : "var(--danger-600)" }}
    >
      {children}
    </p>
  );
}

const STACK_LABELS: Record<string, string> = {
  paperless: "Paperless",
  akaunting: "Akaunting",
  firefly: "Firefly III",
  strapi: "Strapi",
};

export default function SettingsPage() {
  const router = useRouter();

  const [accounts, setAccounts] = useState<EmailAccount[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stack, setStack] = useState<StackConfig | null>(null);

  // add-account form
  const [label, setLabel] = useState("");
  const [email, setEmail] = useState("");
  const [provider, setProvider] = useState("gmail");
  const [password, setPassword] = useState("");
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState("993");
  const [adding, setAdding] = useState(false);
  const [addMsg, setAddMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  // scan status
  const [scanMsg, setScanMsg] = useState<string | null>(null);
  const [scanBusy, setScanBusy] = useState(false);

  // change password
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwMsg, setPwMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [pwBusy, setPwBusy] = useState(false);

  const [signingOut, setSigningOut] = useState(false);

  const loadAccounts = () =>
    api
      .accounts()
      .then(setAccounts)
      .catch((e) => setError(String(e?.message || e)));

  useEffect(() => {
    loadAccounts();
    api
      .stackConfig()
      .then(setStack)
      .catch(() => setStack(null));
  }, []);

  async function toggle(a: EmailAccount) {
    await api.toggleAccount(a.label, !a.active).catch(() => {});
    loadAccounts();
  }

  async function remove(a: EmailAccount) {
    if (!confirm(`Remove "${a.label}"?`)) return;
    await api.deleteAccount(a.label).catch(() => {});
    loadAccounts();
  }

  async function addAccount(e: React.FormEvent) {
    e.preventDefault();
    setAddMsg(null);
    setAdding(true);
    try {
      await api.addAccount({
        label,
        email,
        provider,
        password: password || undefined,
        imap_host: provider === "imap" ? imapHost || undefined : undefined,
        imap_port: provider === "imap" ? Number(imapPort) || undefined : undefined,
      });
      setLabel("");
      setEmail("");
      setPassword("");
      setImapHost("");
      setImapPort("993");
      setProvider("gmail");
      setAddMsg({ tone: "success", text: "Account added." });
      await loadAccounts();
    } catch (err: any) {
      setAddMsg({ tone: "error", text: String(err?.message || err) });
    } finally {
      setAdding(false);
    }
  }

  async function runScan(mode: "incremental" | "full") {
    setScanBusy(true);
    setScanMsg(null);
    try {
      await api.startScan(mode);
      setScanMsg(mode === "full" ? "Full history scan started." : "Recent scan started.");
    } catch (err: any) {
      setScanMsg(`Couldn't start scan: ${String(err?.message || err)}`);
    } finally {
      setScanBusy(false);
    }
  }

  async function runReprocess() {
    setScanBusy(true);
    setScanMsg(null);
    try {
      const r = await api.reprocess();
      setScanMsg(`Reprocessed ${r.scanned} emails (${r.updated} updated).`);
    } catch (err: any) {
      setScanMsg(`Reprocess failed: ${String(err?.message || err)}`);
    } finally {
      setScanBusy(false);
    }
  }

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwMsg(null);
    setPwBusy(true);
    try {
      await api.changePassword(oldPw, newPw);
      setOldPw("");
      setNewPw("");
      setPwMsg({ tone: "success", text: "Password updated." });
    } catch (err: any) {
      setPwMsg({ tone: "error", text: String(err?.message || err) });
    } finally {
      setPwBusy(false);
    }
  }

  async function signOut() {
    setSigningOut(true);
    await api.logout();
    router.replace("/login");
  }

  const stackServices = stack
    ? (["paperless", "akaunting", "firefly", "strapi"] as const)
        .map((k) => ({ key: k, svc: stack[k] }))
        .filter((s) => s.svc)
    : [];

  return (
    <>
      <PageHeader title="Settings" subtitle="Connections, accounts, and preferences" />
      <div className="px-8 py-7 pb-16 lg-fade-up">
        <div className="mx-auto flex max-w-[720px] flex-col gap-[18px]">
          {/* ── Connected inboxes ── */}
          <Card className="p-5.5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <SectionTitle>Connected inboxes</SectionTitle>
              <StatusPill tone="info">
                {accounts ? `${accounts.length} account${accounts.length === 1 ? "" : "s"}` : "—"}
              </StatusPill>
            </div>

            <PageState loading={accounts === null} error={error}>
              {accounts && accounts.length === 0 && (
                <p className="text-sm text-ink-500">
                  No inboxes connected yet. Add one below to start scanning for receipts.
                </p>
              )}

              {accounts && accounts.length > 0 && (
                <div className="flex flex-col gap-2.5">
                  {accounts.map((a) => (
                    <div
                      key={a.label}
                      className="flex items-center gap-3.5 rounded-md bg-surface-sunken px-4 py-3"
                    >
                      <span
                        className="flex h-[38px] w-[38px] flex-none items-center justify-center rounded-[10px] bg-white"
                        style={{ color: "var(--coral-600)", boxShadow: "var(--shadow-xs)" }}
                      >
                        <Icon name="mail" size={18} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-ink-900">
                          {a.label}
                        </div>
                        <div className="truncate text-xs text-ink-500">
                          {a.email} · {a.provider}
                          {!a.has_password && " · no app password"}
                        </div>
                      </div>
                      <StatusPill tone={a.active ? "success" : "neutral"}>
                        {a.active ? "Active" : "Paused"}
                      </StatusPill>
                      <Button size="sm" variant="secondary" onClick={() => toggle(a)}>
                        {a.active ? "Pause" : "Resume"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Remove ${a.label}`}
                        onClick={() => remove(a)}
                        style={{ color: "var(--danger-600)" }}
                      >
                        <Icon name="trash" size={16} />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </PageState>

            {/* Add account form */}
            <form
              onSubmit={addAccount}
              className="flex flex-col gap-3 border-t border-line-faint pt-4"
            >
              <span className="font-display text-sm font-bold text-ink-900">Add account</span>
              <div className="flex gap-3">
                <Field label="Label">
                  <input
                    required
                    className={inputCls}
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="personal"
                  />
                </Field>
                <Field label="Email address">
                  <input
                    required
                    type="email"
                    className={inputCls}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                  />
                </Field>
              </div>
              <div className="flex gap-3">
                <Field label="Provider">
                  <select
                    className={`${inputCls} cursor-pointer`}
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    <option value="gmail">Gmail</option>
                    <option value="imap">Other IMAP</option>
                  </select>
                </Field>
                <Field label="App password (optional)">
                  <input
                    type="password"
                    className={`${inputCls} font-mono tracking-[.08em]`}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="xxxx xxxx xxxx xxxx"
                  />
                </Field>
              </div>
              {provider === "imap" && (
                <div className="flex gap-3">
                  <Field label="IMAP host">
                    <input
                      className={`${inputCls} font-mono`}
                      value={imapHost}
                      onChange={(e) => setImapHost(e.target.value)}
                      placeholder="imap.example.com"
                    />
                  </Field>
                  <label className="flex w-[120px] flex-none flex-col gap-1.5">
                    <span className={labelCls}>IMAP port</span>
                    <input
                      className={`${inputCls} font-mono`}
                      value={imapPort}
                      onChange={(e) => setImapPort(e.target.value)}
                      placeholder="993"
                    />
                  </label>
                </div>
              )}
              <p className="text-xs leading-relaxed text-ink-500">
                For Gmail, create an app password at myaccount.google.com → Security → App
                passwords. Stored encrypted and used for IMAP access.
              </p>
              {addMsg && <Note tone={addMsg.tone}>{addMsg.text}</Note>}
              <div>
                <Button type="submit" size="sm" disabled={adding}>
                  <Icon name="plus" size={16} />
                  {adding ? "Adding…" : "Add account"}
                </Button>
              </div>
            </form>
          </Card>

          {/* ── Scan settings ── */}
          <Card className="p-5.5 flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <SectionTitle>Scan settings</SectionTitle>
              <span className="text-[12.5px] text-ink-500">
                Pull new receipts from your inboxes, or rebuild from existing emails.
              </span>
            </div>
            <div className="flex flex-wrap gap-2.5">
              <Button
                size="sm"
                variant="primary"
                disabled={scanBusy}
                onClick={() => runScan("incremental")}
              >
                <Icon name="sparkle" size={16} />
                Scan recent
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={scanBusy}
                onClick={() => runScan("full")}
              >
                <Icon name="clock" size={16} />
                Full history
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={scanBusy}
                onClick={runReprocess}
              >
                <Icon name="refresh" size={16} />
                Reprocess
              </Button>
            </div>
            {scanMsg && <p className="text-[13px] font-medium text-ink-600">{scanMsg}</p>}
          </Card>

          {/* ── Integrations ── */}
          {stackServices.length > 0 && (
            <Card className="p-5.5 flex flex-col gap-4">
              <SectionTitle>Integrations</SectionTitle>
              <div className="flex flex-col gap-2.5">
                {stackServices.map(({ key, svc }) => (
                  <div
                    key={key}
                    className="flex items-center gap-3 rounded-md bg-surface-sunken px-4 py-3"
                  >
                    <span
                      className="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] bg-white"
                      style={{ color: "var(--violet-600)", boxShadow: "var(--shadow-xs)" }}
                    >
                      <Icon name="grid" size={17} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-ink-900">
                        {STACK_LABELS[key] || key}
                      </div>
                      {svc.url && (
                        <div className="truncate text-xs text-ink-500">{svc.url}</div>
                      )}
                    </div>
                    <StatusPill tone={svc.enabled ? "success" : "neutral"}>
                      {svc.enabled ? "Enabled" : "Disabled"}
                    </StatusPill>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* ── Security ── */}
          {!supabaseConfigured ? (
            <Card className="p-5.5 flex flex-col gap-4">
              <div className="flex items-center gap-2.5">
                <Icon name="shield" size={18} style={{ color: "var(--ink-500)" }} />
                <SectionTitle>Security</SectionTitle>
              </div>
              <form onSubmit={changePassword} className="flex flex-col gap-3">
                <div className="flex gap-3">
                  <Field label="Current password">
                    <input
                      required
                      type="password"
                      className={inputCls}
                      value={oldPw}
                      onChange={(e) => setOldPw(e.target.value)}
                    />
                  </Field>
                  <Field label="New password">
                    <input
                      required
                      type="password"
                      className={inputCls}
                      value={newPw}
                      onChange={(e) => setNewPw(e.target.value)}
                    />
                  </Field>
                </div>
                {pwMsg && <Note tone={pwMsg.tone}>{pwMsg.text}</Note>}
                <div>
                  <Button type="submit" size="sm" disabled={pwBusy}>
                    {pwBusy ? "Saving…" : "Change password"}
                  </Button>
                </div>
              </form>
            </Card>
          ) : (
            <Card className="p-5.5 flex flex-col gap-3">
              <div className="flex items-center gap-2.5">
                <Icon name="shield" size={18} style={{ color: "var(--ink-500)" }} />
                <SectionTitle>Security</SectionTitle>
              </div>
              <p className="text-[13px] leading-relaxed text-ink-500">
                You&apos;re signed in with Supabase — manage your password and Google
                connection from your account provider.
              </p>
            </Card>
          )}

          {/* ── Danger zone ── */}
          <Card className="p-5.5 flex items-center gap-4 border-danger-100">
            <div className="flex-1">
              <div className="font-display text-base font-bold text-ink-900">Danger zone</div>
              <div className="text-[13px] text-ink-500">
                Sign out of this device. You can sign back in anytime.
              </div>
            </div>
            <Button variant="secondary" size="sm" disabled={signingOut} onClick={signOut}>
              <Icon name="logout" size={16} />
              {signingOut ? "Signing out…" : "Sign out"}
            </Button>
          </Card>
        </div>
      </div>
    </>
  );
}
