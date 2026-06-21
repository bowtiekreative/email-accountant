"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Icon,
  Card,
  StatusPill,
  Chip,
  EmptyState,
  PageState,
  categoryStyle,
  accent,
  accentTint,
} from "@/lib/ui";
import { PageHeader, HeaderSearch } from "@/components/PageHeader";
import { api, fmt, type Transaction } from "@/lib/api";

const CURRENCY = "USD";
const GRID = "104px 1.6fr 1fr 130px 120px 28px";

const fmtDate = (s?: string) => {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d.getTime())) return s.slice(0, 10);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

// Special filters beyond category chips.
type SpecialFilter = "all" | "needs_review" | "reviewed";

export default function TransactionsPage() {
  const year = new Date().getFullYear();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<string | null>(null); // null = no category chip selected
  const [special, setSpecial] = useState<SpecialFilter>("all");

  function reload() {
    setRows(null);
    setError(null);
    api
      .transactions({ year, currency: CURRENCY, q, limit: 200 })
      .then(setRows)
      .catch((e) => setError(e?.message || "Failed to load transactions"));
  }

  // Debounce on search; reload on mount.
  useEffect(() => {
    const t = setTimeout(reload, 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  // Distinct categories present in the data, in stable order.
  const categories = useMemo(() => {
    if (!rows) return [];
    const seen: string[] = [];
    for (const r of rows) {
      const c = r.category;
      if (c && !seen.includes(c)) seen.push(c);
    }
    return seen;
  }, [rows]);

  // Client-side combined filter (search already applied server-side via q).
  const filtered = useMemo(() => {
    if (!rows) return [];
    return rows.filter((r) => {
      if (category && r.category !== category) return false;
      if (special === "reviewed" && !r.reviewed) return false;
      if (special === "needs_review" && !r.needs_review) return false;
      return true;
    });
  }, [rows, category, special]);

  function selectAll() {
    setCategory(null);
    setSpecial("all");
  }

  return (
    <>
      <PageHeader
        title="Transactions"
        subtitle="Every expense Ledger found, sorted."
        showScan
        onScanned={reload}
      >
        <HeaderSearch value={q} onChange={setQ} />
      </PageHeader>

      <div className="px-8 py-7 pb-16 lg-fade-up">
        <PageState loading={rows === null && !error} error={error}>
          {/* Filter chips */}
          <div className="mb-5 flex flex-wrap items-center gap-2.5">
            <Chip
              active={category === null && special === "all"}
              onClick={selectAll}
            >
              All
            </Chip>
            {categories.map((c) => {
              const cs = categoryStyle(c);
              return (
                <Chip
                  key={c}
                  icon={cs.icon}
                  active={category === c}
                  onClick={() => setCategory(category === c ? null : c)}
                >
                  {c}
                </Chip>
              );
            })}
            <Chip
              icon="clock"
              active={special === "needs_review"}
              onClick={() =>
                setSpecial(special === "needs_review" ? "all" : "needs_review")
              }
            >
              Needs review
            </Chip>
            <Chip
              icon="check"
              active={special === "reviewed"}
              onClick={() =>
                setSpecial(special === "reviewed" ? "all" : "reviewed")
              }
            >
              Verified
            </Chip>
          </div>

          {/* Table */}
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <div className="min-w-[760px]">
                {/* Header row */}
                <div
                  className="grid items-center gap-3.5 border-b border-line bg-surface-sunken px-[22px] py-3.5"
                  style={{ gridTemplateColumns: GRID }}
                >
                  <span className="text-[11.5px] font-bold uppercase tracking-wide text-ink-500">
                    Date
                  </span>
                  <span className="text-[11.5px] font-bold uppercase tracking-wide text-ink-500">
                    Vendor
                  </span>
                  <span className="text-[11.5px] font-bold uppercase tracking-wide text-ink-500">
                    Category
                  </span>
                  <span className="text-right text-[11.5px] font-bold uppercase tracking-wide text-ink-500">
                    Amount
                  </span>
                  <span className="text-[11.5px] font-bold uppercase tracking-wide text-ink-500">
                    Status
                  </span>
                  <span />
                </div>

                {/* Rows */}
                {filtered.length === 0 ? (
                  <EmptyState
                    icon="list"
                    title="No transactions match that filter."
                  />
                ) : (
                  filtered.map((t) => {
                    const cs = categoryStyle(t.category);
                    const verified = !!t.reviewed;
                    return (
                      <Link
                        key={t.id}
                        href={`/transactions/${t.id}`}
                        className="grid items-center gap-3.5 border-b border-line-faint px-[22px] py-[15px] transition-colors hover:bg-violet-50"
                        style={{ gridTemplateColumns: GRID }}
                      >
                        {/* Date */}
                        <span className="font-mono text-[12.5px] text-ink-500">
                          {fmtDate(t.email_date)}
                        </span>

                        {/* Vendor */}
                        <div className="flex min-w-0 items-center gap-[11px]">
                          <span
                            className="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-[9px]"
                            style={{
                              background: accentTint(cs.accent),
                              color: accent(cs.accent),
                            }}
                          >
                            <Icon name={cs.icon} size={16} />
                          </span>
                          <span className="truncate font-display text-[14.5px] font-semibold text-ink-900">
                            {t.merchant_name || "—"}
                          </span>
                        </div>

                        {/* Category */}
                        <span className="inline-flex items-center gap-[7px]">
                          <span
                            className="h-2 w-2 flex-none rounded-pill"
                            style={{ background: accent(cs.accent) }}
                          />
                          <span className="truncate text-[13px] text-ink-700">
                            {t.category || "Uncategorized"}
                          </span>
                        </span>

                        {/* Amount */}
                        <span className="text-right font-mono text-[15px] font-bold text-ink-900">
                          {fmt(t.amount, t.currency || CURRENCY)}
                        </span>

                        {/* Status */}
                        <span>
                          {verified ? (
                            <StatusPill tone="success">Verified</StatusPill>
                          ) : (
                            <StatusPill tone="warning">Pending</StatusPill>
                          )}
                        </span>

                        {/* Chevron */}
                        <span className="flex justify-center text-ink-300">
                          <Icon name="arrowRight" size={16} />
                        </span>
                      </Link>
                    );
                  })
                )}
              </div>
            </div>
          </Card>
        </PageState>
      </div>
    </>
  );
}
