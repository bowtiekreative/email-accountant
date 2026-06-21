"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Card,
  SectionTitle,
  EmptyState,
  PageState,
  accent,
  ACCENTS,
} from "@/lib/ui";
import { PageHeader } from "@/components/PageHeader";
import { api, fmt, type Overview } from "@/lib/api";

export default function InsightsPage() {
  const year = new Date().getFullYear();
  const currency = "USD";

  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const ov = await api.overview(year, currency);
        if (!cancelled) setOverview(ov);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || "Failed to load insights");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Last 6 months of expense trend.
  const trend = useMemo(() => {
    const all = overview?.monthly_trend ?? [];
    return all.slice(-6);
  }, [overview]);
  const trendMax = useMemo(
    () => Math.max(1, ...trend.map((t) => t.expense || 0)),
    [trend]
  );

  // Top 5 categories.
  const categories = useMemo(
    () => (overview?.by_category ?? []).slice(0, 5),
    [overview]
  );
  const catTotal = useMemo(
    () => categories.reduce((s, c) => s + (c.total || 0), 0),
    [categories]
  );

  // Build conic-gradient string + per-slice cumulative percentages.
  const { donutStyle, legend } = useMemo(() => {
    if (!catTotal) {
      return {
        donutStyle: { background: "var(--surface-sunken)" } as React.CSSProperties,
        legend: [] as { name: string; color: string; pct: number }[],
      };
    }
    const stops: string[] = [];
    const leg: { name: string; color: string; pct: number }[] = [];
    let cursor = 0;
    categories.forEach((c, i) => {
      const color = accent(ACCENTS[i % ACCENTS.length]);
      const pct = (c.total / catTotal) * 100;
      const start = cursor;
      const end = cursor + pct;
      stops.push(`${color} ${start}% ${end}%`);
      leg.push({ name: c.name, color, pct });
      cursor = end;
    });
    return {
      donutStyle: {
        background: `conic-gradient(${stops.join(", ")})`,
      } as React.CSSProperties,
      legend: leg,
    };
  }, [categories, catTotal]);

  // Top 5 vendors.
  const vendors = useMemo(
    () => (overview?.by_merchant ?? []).slice(0, 5),
    [overview]
  );
  const vendorMax = useMemo(
    () => Math.max(1, ...vendors.map((v) => v.total || 0)),
    [vendors]
  );

  const hasData =
    !!overview &&
    (trend.some((t) => t.expense) ||
      categories.length > 0 ||
      vendors.length > 0);

  return (
    <>
      <PageHeader title="Insights" subtitle="Where your money went this month" />

      <div className="px-8 py-7 pb-16 lg-fade-up">
        <PageState loading={loading} error={error}>
          {!hasData ? (
            <EmptyState
              icon="bars"
              title="No spending to chart yet"
              body="Scan your inbox to see your trends and top categories."
            />
          ) : (
            <div className="flex flex-col gap-5">
              {/* ── Spending trend ── */}
              <Card className="p-6">
                <div className="mb-1.5 flex items-baseline justify-between">
                  <SectionTitle>Spending trend</SectionTitle>
                  <span className="text-[12.5px] text-ink-500">Last 6 months</span>
                </div>
                <div className="flex items-end gap-[18px] pt-[18px]" style={{ height: 208 }}>
                  {trend.map((t, i) => {
                    const pct = ((t.expense || 0) / trendMax) * 100;
                    const month = monthLabel(t.month);
                    return (
                      <div
                        key={i}
                        className="flex h-full flex-1 flex-col items-center justify-end gap-[9px]"
                      >
                        <span className="font-mono text-[12px] font-semibold text-ink-500">
                          {fmt(t.expense, currency)}
                        </span>
                        <div className="flex w-[64%] flex-1 items-end">
                          <div
                            className="w-full rounded-t"
                            style={{
                              height: `${pct}%`,
                              background:
                                "linear-gradient(180deg, var(--violet-500), var(--violet-600))",
                            }}
                          />
                        </div>
                        <span className="text-[12.5px] font-medium text-ink-600">
                          {month}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Card>

              {/* ── Category + vendors grid ── */}
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                {/* By category */}
                <Card className="p-6">
                  <SectionTitle>By category</SectionTitle>
                  <div className="mt-4 flex items-center gap-6">
                    <div
                      className="relative flex-none"
                      style={{ width: 168, height: 168 }}
                    >
                      <div
                        className="absolute inset-0 rounded-pill"
                        style={donutStyle}
                      />
                      {/* Inner white circle → ring */}
                      <div
                        className="absolute rounded-pill bg-surface"
                        style={{ inset: 22 }}
                      />
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="font-mono text-[19px] font-bold text-ink-900">
                          {fmt(catTotal, currency)}
                        </span>
                        <span className="text-[11px] text-ink-500">this month</span>
                      </div>
                    </div>
                    <div className="flex flex-1 flex-col gap-[11px]">
                      {legend.map((b, i) => (
                        <div key={i} className="flex items-center gap-[10px]">
                          <span
                            className="h-2.5 w-2.5 flex-none rounded-pill"
                            style={{ background: b.color }}
                          />
                          <span className="flex-1 truncate text-[13px] text-ink-700">
                            {b.name}
                          </span>
                          <span className="font-mono text-[12.5px] text-ink-500">
                            {b.pct.toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </Card>

                {/* Top vendors */}
                <Card className="p-6">
                  <SectionTitle>Top vendors</SectionTitle>
                  <div className="mt-4 flex flex-col gap-[15px]">
                    {vendors.map((v, i) => {
                      const pct = ((v.total || 0) / vendorMax) * 100;
                      return (
                        <div key={i} className="flex flex-col gap-[7px]">
                          <div className="flex items-baseline justify-between">
                            <span className="truncate text-[13.5px] font-medium text-ink-800">
                              {v.name}
                            </span>
                            <span className="ml-3 flex-none font-mono text-[13px] font-semibold text-ink-700">
                              {fmt(v.total, currency)}
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-pill bg-surface-sunken">
                            <div
                              className="h-full rounded-pill"
                              style={{
                                width: `${pct}%`,
                                background:
                                  "linear-gradient(90deg, var(--violet-500), var(--violet-600))",
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              </div>
            </div>
          )}
        </PageState>
      </div>
    </>
  );
}

// monthly_trend month is a "YYYY-MM" string → short month label ("Jan").
function monthLabel(month: string): string {
  if (!month) return "—";
  const parts = month.split("-");
  const m = Number(parts[1]);
  if (m >= 1 && m <= 12) {
    return new Date(2000, m - 1, 1).toLocaleDateString("en-US", {
      month: "short",
    });
  }
  return month;
}
