"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  BentoTile,
  Icon,
  SectionTitle,
  PageState,
  accent,
  accentTint,
  accentFor,
  ACCENTS,
} from "@/lib/ui";
import { PageHeader } from "@/components/PageHeader";
import {
  api,
  fmt,
  type NetWorthAccount,
  type NetWorthProjection,
  type NetWorthSummary,
  type WealthAdvice,
} from "@/lib/api";

const CURRENCY = "USD";

export default function InvestmentsPage() {
  const [summary, setSummary] = useState<NetWorthSummary | null>(null);
  const [advice, setAdvice] = useState<WealthAdvice | null>(null);
  const [projection, setProjection] = useState<NetWorthProjection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline "add account" form state.
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"asset" | "liability">("asset");
  const [balance, setBalance] = useState("");
  const [adding, setAdding] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [s, a, p] = await Promise.all([
        api.nwSummary(CURRENCY),
        api.wealthAdvice(CURRENCY).catch(() => null),
        api.nwProjection(CURRENCY, 0.07, 30).catch(() => null),
      ]);
      setSummary(s);
      setAdvice(a);
      setProjection(p);
    } catch (e: any) {
      setError(e?.message || "Failed to load investments");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function addAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || adding) return;
    setAdding(true);
    try {
      await api.nwAddAccount({
        name: name.trim(),
        kind,
        category: kind === "asset" ? "investment" : "loan",
        currency: CURRENCY,
        balance: balance ? Number(balance) : 0,
      });
      setName("");
      setBalance("");
      setKind("asset");
      await load();
    } catch {
      /* surfaced on next load */
    } finally {
      setAdding(false);
    }
  }

  // ── Donut allocation from asset categories ──
  const { donutStyle, legend, assetTotal } = useMemo(() => {
    const cats = (summary?.by_category ?? []).filter((c) => c.kind === "asset");
    const total = cats.reduce((s, c) => s + Math.abs(c.total || 0), 0);
    if (!total) {
      return {
        donutStyle: { background: "var(--surface-sunken)" } as React.CSSProperties,
        legend: [] as { name: string; color: string; pct: number }[],
        assetTotal: 0,
      };
    }
    const stops: string[] = [];
    const leg: { name: string; color: string; pct: number }[] = [];
    let cursor = 0;
    cats.forEach((c, i) => {
      const color = accent(ACCENTS[i % ACCENTS.length]);
      const pct = (Math.abs(c.total) / total) * 100;
      stops.push(`${color} ${cursor}% ${cursor + pct}%`);
      leg.push({ name: c.category, color, pct });
      cursor += pct;
    });
    return {
      donutStyle: {
        background: `conic-gradient(${stops.join(", ")})`,
      } as React.CSSProperties,
      legend: leg,
      assetTotal: total,
    };
  }, [summary]);

  const accounts = summary?.accounts ?? [];

  return (
    <>
      <PageHeader
        title="Investments"
        subtitle="Your portfolio and net worth at a glance"
      />

      <div className="px-8 py-7 pb-16 lg-fade-up">
        <PageState loading={loading} error={error}>
          <div className="flex flex-col gap-5">
            {/* ── Stat bento tiles ── */}
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
              <StatTile
                accent="violet"
                icon="wallet"
                label="Net worth"
                value={fmt(summary?.net_worth, CURRENCY)}
              />
              <StatTile
                accent="teal"
                icon="trending"
                label="Assets"
                value={fmt(summary?.assets, CURRENCY)}
              />
              <StatTile
                accent="coral"
                icon="scales"
                label="Liabilities"
                value={fmt(summary?.liabilities, CURRENCY)}
              />
              <StatTile
                accent="amber"
                icon="zap"
                label="Suggested monthly invest"
                value={fmt(advice?.recommended_monthly_investment, CURRENCY)}
              />
            </div>

            {/* ── Accounts + allocation ── */}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.5fr_1fr]">
              {/* Accounts table */}
              <Card className="overflow-hidden">
                <div className="grid grid-cols-[1.6fr_110px_130px_92px] items-center gap-3.5 border-b border-line bg-surface-sunken px-[22px] py-3.5">
                  <span className="text-[11.5px] font-bold uppercase tracking-[0.04em] text-ink-500">
                    Holding
                  </span>
                  <span className="text-[11.5px] font-bold uppercase tracking-[0.04em] text-ink-500">
                    Category
                  </span>
                  <span className="text-right text-[11.5px] font-bold uppercase tracking-[0.04em] text-ink-500">
                    Value
                  </span>
                  <span className="text-right text-[11.5px] font-bold uppercase tracking-[0.04em] text-ink-500">
                    Type
                  </span>
                </div>

                {accounts.length === 0 ? (
                  <div className="flex flex-col gap-4 px-[22px] py-8">
                    <p className="text-sm text-ink-500">
                      No accounts yet — add your investments, savings, and debts
                      to see the full picture.
                    </p>
                    <form
                      onSubmit={addAccount}
                      className="flex flex-wrap items-center gap-2.5"
                    >
                      <input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Account name"
                        className="h-11 min-w-[160px] flex-1 rounded-sm border border-line-strong bg-surface px-3.5 font-body text-sm text-ink-900 outline-none placeholder:text-ink-400 focus:border-violet-500"
                      />
                      <select
                        value={kind}
                        onChange={(e) =>
                          setKind(e.target.value as "asset" | "liability")
                        }
                        className="h-11 rounded-sm border border-line-strong bg-surface px-3 font-body text-sm text-ink-900 outline-none focus:border-violet-500"
                      >
                        <option value="asset">Asset</option>
                        <option value="liability">Liability</option>
                      </select>
                      <input
                        value={balance}
                        onChange={(e) => setBalance(e.target.value)}
                        placeholder="Balance"
                        type="number"
                        className="h-11 w-32 rounded-sm border border-line-strong bg-surface px-3.5 font-body text-sm text-ink-900 outline-none placeholder:text-ink-400 focus:border-violet-500"
                      />
                      <Button type="submit" size="sm" disabled={adding}>
                        <Icon name="plus" size={15} />
                        {adding ? "Adding…" : "Add account"}
                      </Button>
                    </form>
                  </div>
                ) : (
                  accounts.map((a: NetWorthAccount) => {
                    const a2 = accentFor(a.name);
                    return (
                      <div
                        key={a.id}
                        className="grid grid-cols-[1.6fr_110px_130px_92px] items-center gap-3.5 border-b border-line-faint px-[22px] py-[15px] last:border-b-0"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <span
                            className="flex h-[38px] w-[38px] flex-none items-center justify-center rounded-[10px] font-mono text-xs font-bold"
                            style={{
                              background: accentTint(a2),
                              color: accent(a2),
                            }}
                          >
                            {initials(a.name)}
                          </span>
                          <span className="truncate font-display text-[14.5px] font-semibold text-ink-900">
                            {a.name}
                          </span>
                        </div>
                        <span className="truncate text-[13px] capitalize text-ink-500">
                          {(a.category || "").replace(/_/g, " ")}
                        </span>
                        <span className="text-right font-mono text-[14.5px] font-bold text-ink-900">
                          {fmt(a.balance, a.currency || CURRENCY)}
                        </span>
                        <span className="flex justify-end">
                          <KindTag kind={a.kind} />
                        </span>
                      </div>
                    );
                  })
                )}
              </Card>

              {/* Allocation donut */}
              <Card className="p-6">
                <SectionTitle>Allocation</SectionTitle>
                <div className="mt-4 flex flex-col items-center gap-[18px]">
                  <div className="relative flex-none" style={{ width: 170, height: 170 }}>
                    <div className="absolute inset-0 rounded-pill" style={donutStyle} />
                    <div
                      className="absolute rounded-pill bg-surface"
                      style={{ inset: 24 }}
                    />
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="font-mono text-[18px] font-bold text-ink-900">
                        {fmt(summary?.assets, CURRENCY)}
                      </span>
                      <span className="text-[11px] text-ink-500">in assets</span>
                    </div>
                  </div>
                  <div className="flex w-full flex-col gap-[9px]">
                    {legend.length === 0 ? (
                      <span className="text-center text-[13px] text-ink-400">
                        No assets to chart yet.
                      </span>
                    ) : (
                      legend.map((b, i) => (
                        <div key={i} className="flex items-center gap-[10px]">
                          <span
                            className="h-2.5 w-2.5 flex-none rounded-pill"
                            style={{ background: b.color }}
                          />
                          <span className="flex-1 truncate text-[13px] capitalize text-ink-700">
                            {b.name.replace(/_/g, " ")}
                          </span>
                          <span className="font-mono text-[12.5px] text-ink-500">
                            {b.pct.toFixed(0)}%
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </Card>
            </div>

            {/* ── Read-only info banner ── */}
            <div className="flex items-center gap-[11px] rounded-[14px] border border-violet-100 bg-violet-50 p-[14px_18px] text-[13.5px] text-violet-700">
              <Icon name="info" size={18} className="flex-none" />
              <span>
                Linked read-only. Ledger never moves money — it just helps you
                see the full picture.
              </span>
            </div>

            {/* ── Projected net worth line ── */}
            {projection && (
              <p className="px-1 text-[13px] text-ink-500">
                At ~7%/yr you could reach{" "}
                <span className="font-mono font-semibold text-ink-700">
                  {fmt(projection.future_value, CURRENCY)}
                </span>{" "}
                in 30 years.
              </p>
            )}
          </div>
        </PageState>
      </div>
    </>
  );
}

function StatTile({
  accent: a,
  icon,
  label,
  value,
}: {
  accent: (typeof ACCENTS)[number];
  icon: string;
  label: string;
  value: string;
}) {
  return (
    <BentoTile accent={a} icon={icon as any}>
      <div className="mt-auto flex flex-col gap-px pt-3">
        <span className="font-mono text-[27px] font-semibold leading-[1.05] tracking-[-0.01em] text-ink-900">
          {value}
        </span>
        <span className="text-[12.5px] font-medium text-ink-600">{label}</span>
      </div>
    </BentoTile>
  );
}

function KindTag({ kind }: { kind: "asset" | "liability" }) {
  const isAsset = kind === "asset";
  const a = isAsset ? "teal" : "coral";
  return (
    <span
      className="inline-flex items-center rounded-pill px-2.5 py-1 text-[11.5px] font-semibold capitalize"
      style={{ background: accentTint(a), color: accent(a) }}
    >
      {kind}
    </span>
  );
}

function initials(name: string): string {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "—";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}
