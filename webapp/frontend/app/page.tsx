"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Icon,
  BentoTile,
  Chip,
  EmptyState,
  PageState,
  categoryStyle,
  accent,
  type Accent,
  type IconName,
} from "@/lib/ui";
import { PageHeader, HeaderSearch } from "@/components/PageHeader";
import { api, fmt, type Overview, type Transaction } from "@/lib/api";

export default function GalleryPage() {
  const year = new Date().getFullYear();
  const currency = "USD";

  const [overview, setOverview] = useState<Overview | null>(null);
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [activeCat, setActiveCat] = useState<string>("__all__");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [ov, tx] = await Promise.all([
        api.overview(year, currency),
        api.transactions({ year, currency, q, limit: 60 }),
      ]);
      setOverview(ov);
      setTxns(tx);
    } catch (e: any) {
      setError(e?.message || "Failed to load receipts");
    } finally {
      setLoading(false);
    }
  }

  // Initial load + re-fetch when the header search query changes.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [ov, tx] = await Promise.all([
          api.overview(year, currency),
          api.transactions({ year, currency, q, limit: 60 }),
        ]);
        if (cancelled) return;
        setOverview(ov);
        setTxns(tx);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || "Failed to load receipts");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const totals = overview?.totals_by_currency?.[currency];

  // Distinct categories present in the loaded receipts → filter chips.
  const categories = useMemo(() => {
    const set = new Set<string>();
    txns.forEach((t) => {
      if (t.category) set.add(t.category);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [txns]);

  // Client-side filter by selected chip + header search (vendor or category).
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return txns.filter((t) => {
      if (activeCat !== "__all__" && t.category !== activeCat) return false;
      if (!needle) return true;
      const vendor = (t.merchant_name || "").toLowerCase();
      const cat = (t.category || "").toLowerCase();
      return vendor.includes(needle) || cat.includes(needle);
    });
  }, [txns, activeCat, q]);

  const topCategory = overview?.by_category?.[0];
  const topStyle = categoryStyle(topCategory?.name);

  const monthYear = new Date().toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  const stats: {
    accent: Accent;
    icon: IconName;
    value: string;
    label: string;
  }[] = [
    {
      accent: "amber",
      icon: "wallet",
      value: fmt(totals?.expense, currency),
      label: "Spent this month",
    },
    {
      accent: "violet",
      icon: "mail",
      value: String(totals?.transaction_count ?? 0),
      label: "Receipts captured",
    },
    {
      accent: "coral",
      icon: "clock",
      value: String(overview?.needs_review ?? 0),
      label: "Pending review",
    },
    {
      accent: topCategory ? topStyle.accent : "sky",
      icon: topCategory ? topStyle.icon : "utensils",
      value: topCategory?.name || "—",
      label: "Top category",
    },
  ];

  return (
    <>
      <PageHeader
        title="Receipt gallery"
        subtitle={`${filtered.length} receipts found in your inbox · ${monthYear}`}
        showScan
        onScanned={load}
      >
        <HeaderSearch value={q} onChange={setQ} />
      </PageHeader>

      <div className="px-8 py-7 pb-16 lg-fade-up">
        <PageState loading={loading} error={error}>
          {/* Bento stat tiles */}
          <div className="mb-[30px] grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((s, i) => (
              <BentoTile key={i} accent={s.accent} icon={s.icon}>
                <div className="mt-auto flex flex-col gap-px">
                  <span
                    className="font-mono font-semibold text-ink-900"
                    style={{
                      fontSize: 29,
                      lineHeight: 1.05,
                      letterSpacing: "-0.01em",
                    }}
                  >
                    {s.value}
                  </span>
                  <span className="text-[12.5px] font-medium text-ink-600">
                    {s.label}
                  </span>
                </div>
              </BentoTile>
            ))}
          </div>

          {/* Category filter chips */}
          <div className="mb-[22px] flex flex-wrap items-center gap-[9px]">
            <Chip
              active={activeCat === "__all__"}
              onClick={() => setActiveCat("__all__")}
            >
              All receipts
            </Chip>
            {categories.map((cat) => {
              const cs = categoryStyle(cat);
              return (
                <Chip
                  key={cat}
                  icon={cs.icon}
                  active={activeCat === cat}
                  onClick={() => setActiveCat(cat)}
                >
                  {cat}
                </Chip>
              );
            })}
          </div>

          {/* Receipt cards grid */}
          {filtered.length === 0 ? (
            <EmptyState
              icon="search"
              title="No receipts match that"
              body="Try a different vendor name, or clear your filters to see everything in your inbox."
            />
          ) : (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">
              {filtered.map((t) => (
                <ReceiptCard key={t.id} t={t} />
              ))}
            </div>
          )}
        </PageState>
      </div>
    </>
  );
}

function ReceiptCard({ t }: { t: Transaction }) {
  const cs = categoryStyle(t.category);
  const color = accent(cs.accent);
  const vendor = t.merchant_name || "Unknown vendor";
  const reviewed = !!t.reviewed || !t.needs_review;
  const amountLabel = fmt(t.amount, t.currency);
  const date = t.email_date
    ? new Date(t.email_date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      })
    : "—";

  return (
    <Link
      href={`/transactions/${t.id}`}
      className="group flex min-h-[236px] flex-col overflow-hidden rounded-[18px] border border-line bg-surface transition-all duration-200 hover:-translate-y-[3px] hover:border-line-strong hover:shadow-lg"
    >
      {/* Sunken preview area */}
      <div className="relative flex flex-1 items-center justify-center bg-surface-sunken p-[18px]">
        {/* Category icon chip */}
        <span
          className="absolute left-3 top-3 flex h-[30px] w-[30px] items-center justify-center rounded-[9px] bg-white"
          style={{ color, boxShadow: "var(--shadow-xs)" }}
        >
          <Icon name={cs.icon} size={16} />
        </span>

        {/* Reviewed status badge */}
        {reviewed && (
          <span
            className="absolute right-3 top-3 flex h-[30px] w-[30px] items-center justify-center rounded-pill text-white"
            style={{
              background: "var(--success-500)",
              boxShadow: "var(--shadow-xs)",
            }}
          >
            <Icon name="check" size={16} />
          </span>
        )}

        {/* Paper receipt mock */}
        <div
          className="relative w-full max-w-[188px] bg-white"
          style={{
            borderRadius: "10px 10px 3px 3px",
            boxShadow:
              "0 6px 18px -8px rgba(27,26,34,.22),0 1px 0 rgba(27,26,34,.04)",
          }}
        >
          <div
            style={{
              height: 4,
              background: color,
              borderRadius: "10px 10px 0 0",
              opacity: 0.9,
            }}
          />
          <div className="px-[15px] pb-1 pt-[13px]">
            <div className="truncate text-center font-mono text-[11px] font-semibold uppercase tracking-[0.02em] text-ink-900">
              {vendor}
            </div>
            <div
              className="my-[9px] mb-[11px] h-px"
              style={{
                background:
                  "repeating-linear-gradient(90deg,var(--line-strong) 0 4px,transparent 4px 8px)",
              }}
            />
            <div className="flex flex-col gap-[7px]">
              <ReceiptLine wA="54%" wB="20%" dark />
              <ReceiptLine wA="40%" wB="16%" />
              <ReceiptLine wA="46%" wB="18%" />
            </div>
            <div
              className="my-[11px] h-px"
              style={{
                background:
                  "repeating-linear-gradient(90deg,var(--line-strong) 0 4px,transparent 4px 8px)",
              }}
            />
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-[9.5px] font-bold tracking-[0.12em] text-ink-500">
                TOTAL
              </span>
              <span className="font-mono text-[14px] font-bold text-ink-900">
                {amountLabel}
              </span>
            </div>
          </div>
          {/* Torn bottom edge */}
          <div
            style={{
              height: 9,
              background: "#fff",
              WebkitMaskImage:
                "linear-gradient(45deg,#000 50%,transparent 51%),linear-gradient(-45deg,#000 50%,transparent 51%)",
              WebkitMaskSize: "11px 11px",
              WebkitMaskRepeat: "repeat-x",
              WebkitMaskPosition: "bottom",
              maskImage:
                "linear-gradient(45deg,#000 50%,transparent 51%),linear-gradient(-45deg,#000 50%,transparent 51%)",
              maskSize: "11px 11px",
              maskRepeat: "repeat-x",
              maskPosition: "bottom",
            }}
          />
        </div>
      </div>

      {/* Footer */}
      <div className="flex flex-none items-center justify-between gap-[10px] border-t border-line-faint bg-white px-4 py-[13px]">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate font-display text-[14.5px] font-semibold text-ink-900">
            {vendor}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="h-[7px] w-[7px] rounded-pill"
              style={{ background: color }}
            />
            <span className="text-[12px] text-ink-500">
              {t.category || "Uncategorized"} · {date}
            </span>
          </span>
        </div>
        <span className="whitespace-nowrap font-mono text-[16px] font-bold text-ink-900">
          {amountLabel}
        </span>
      </div>
    </Link>
  );
}

function ReceiptLine({
  wA,
  wB,
  dark,
}: {
  wA: string;
  wB: string;
  dark?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-[10px]">
      <span
        className="h-[6px] rounded-pill"
        style={{ width: wA, background: dark ? "var(--line-strong)" : "#e6e0d4" }}
      />
      <span
        className="h-[6px] rounded-pill"
        style={{ width: wB, background: dark ? "#dfd9cd" : "#e6e0d4" }}
      />
    </div>
  );
}
