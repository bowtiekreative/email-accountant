"use client";

import { useEffect, useState } from "react";
import { api, type StackConfig, type StackService } from "@/lib/api";

const SERVICES: {
  id: keyof Omit<StackConfig, "routing">;
  label: string;
  blurb: string;
  extra?: { key: string; label: string; secret?: boolean }[];
}[] = [
  { id: "paperless", label: "Paperless-ngx", blurb: "Receipt & invoice OCR + document archive" },
  {
    id: "akaunting",
    label: "Akaunting",
    blurb: "Business accounting (income, expenses, clients)",
    extra: [
      { key: "email", label: "Admin email" },
      { key: "password", label: "Admin password", secret: true },
      { key: "company_id", label: "Company ID" },
      { key: "account_id", label: "Bank account ID" },
    ],
  },
  {
    id: "firefly",
    label: "Firefly III",
    blurb: "Personal budgeting & spending",
    extra: [{ key: "asset_account", label: "Asset account name" }],
  },
  { id: "strapi", label: "Strapi", blurb: "Orchestration glue (unified index, routing, sync log)" },
];

export default function ConnectionsPage() {
  const [config, setConfig] = useState<StackConfig | null>(null);
  const [sync, setSync] = useState<{ status: string; output: string } | null>(null);

  const load = () => api.stackConfig().then(setConfig).catch(() => setConfig(null));
  useEffect(() => {
    load();
    const t = setInterval(() => api.stackSyncStatus().then(setSync).catch(() => {}), 3000);
    return () => clearInterval(t);
  }, []);

  if (!config) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Connections</h1>
          <p className="text-sm text-slate-500">
            Plug in the URL + API token for each self-hosted service. Saved
            locally (never committed); the sync uses these.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {sync && sync.status !== "idle" && (
            <span className="text-xs text-slate-400">sync: {sync.status}</span>
          )}
          <button
            onClick={() => api.startStackSync().then(() => api.stackSyncStatus().then(setSync))}
            disabled={sync?.status === "running"}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            {sync?.status === "running" ? "Syncing…" : "Sync now"}
          </button>
        </div>
      </div>

      {sync?.output && (
        <pre className="max-h-40 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
          {sync.output}
        </pre>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {SERVICES.map((svc) => (
          <ServiceCard key={svc.id} svc={svc} value={config[svc.id]} onSaved={load} />
        ))}
      </div>

      <RoutingCard routing={config.routing} onSaved={load} />
    </div>
  );
}

function ServiceCard({
  svc,
  value,
  onSaved,
}: {
  svc: { id: string; label: string; blurb: string; extra?: { key: string; label: string; secret?: boolean }[] };
  value: StackService;
  onSaved: () => void;
}) {
  const [url, setUrl] = useState(value.url || "");
  const [token, setToken] = useState("");
  const [enabled, setEnabled] = useState(value.enabled);
  const [extra, setExtra] = useState<Record<string, string>>(
    Object.fromEntries((svc.extra || []).map((f) => [f.key, (value as any)[f.key] || ""]))
  );
  const [saving, setSaving] = useState(false);
  const [test, setTest] = useState<{ ok: boolean; detail: string } | null>(null);

  async function save() {
    setSaving(true);
    try {
      const payload: Record<string, any> = { url, enabled, ...extra };
      if (token) payload.token = token; // blank = keep existing
      await api.updateStackConfig(svc.id, payload);
      setToken("");
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-semibold text-ink">{svc.label}</h2>
          <p className="text-xs text-slate-400">{svc.blurb}</p>
        </div>
        <label className="flex items-center gap-1 text-xs text-slate-500">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          enabled
        </label>
      </div>

      <div className="mt-3 space-y-2 text-sm">
        <input
          className="w-full rounded border border-slate-300 px-3 py-1.5"
          placeholder="https://service.yourdomain.com"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <input
          type="password"
          className="w-full rounded border border-slate-300 px-3 py-1.5"
          placeholder={value.has_token ? "API token (•••• saved — leave blank to keep)" : "API token"}
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        {(svc.extra || []).map((f) => (
          <input
            key={f.key}
            type={f.secret ? "password" : "text"}
            className="w-full rounded border border-slate-300 px-3 py-1.5"
            placeholder={
              f.secret && (value as any)[`has_${f.key}`]
                ? `${f.label} (saved — blank to keep)`
                : f.label
            }
            value={extra[f.key]}
            onChange={(e) => setExtra({ ...extra, [f.key]: e.target.value })}
          />
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          onClick={() => api.testStack(svc.id).then(setTest)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Test
        </button>
        {test && (
          <span className={`text-xs ${test.ok ? "text-emerald-600" : "text-rose-600"}`}>
            {test.ok ? "✓ connected" : `✗ ${test.detail}`}
          </span>
        )}
      </div>
    </div>
  );
}

function RoutingCard({ routing, onSaved }: { routing: Record<string, string>; onSaved: () => void }) {
  const [biz, setBiz] = useState(routing.business || "akaunting");
  const [per, setPer] = useState(routing.personal || "firefly");

  async function save() {
    await api.updateStackConfig("routing", { business: biz, personal: per, unknown: per });
    onSaved();
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold text-ink">Routing</h2>
      <p className="text-xs text-slate-400">Where each kind of transaction is sent.</p>
      <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-2">
          Business →
          <select className="rounded border border-slate-300 px-2 py-1" value={biz} onChange={(e) => setBiz(e.target.value)}>
            <option value="akaunting">Akaunting</option>
            <option value="firefly">Firefly</option>
          </select>
        </label>
        <label className="flex items-center gap-2">
          Personal →
          <select className="rounded border border-slate-300 px-2 py-1" value={per} onChange={(e) => setPer(e.target.value)}>
            <option value="firefly">Firefly</option>
            <option value="akaunting">Akaunting</option>
          </select>
        </label>
        <button onClick={save} className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700">
          Save routing
        </button>
      </div>
    </div>
  );
}
