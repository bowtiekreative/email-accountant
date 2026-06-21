"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  Icon,
  PageState,
  SectionTitle,
  Spinner,
} from "@/lib/ui";
import { PageHeader } from "@/components/PageHeader";
import { api, fmt, type GstHst, type TaxReport, type TaxLine } from "@/lib/api";

type FormId = "schedulec" | "t2125" | "gst";

const FORMS: { id: FormId; label: string; currency: string }[] = [
  { id: "schedulec", label: "Schedule C (US)", currency: "USD" },
  { id: "t2125", label: "T2125 (CA)", currency: "CAD" },
  { id: "gst", label: "GST/HST (CA)", currency: "CAD" },
];

const FILE_SLUG: Record<FormId, string> = {
  schedulec: "schedule-c",
  t2125: "t2125",
  gst: "gst-hst",
};

export default function ReportsPage() {
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState<number | null>(null);
  const [form, setForm] = useState<FormId>("schedulec");

  // Page-level bootstrap (year list).
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // The currently loaded report (re-fetched on form/year change).
  const [tax, setTax] = useState<TaxReport | null>(null);
  const [gst, setGst] = useState<GstHst | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const currentForm = FORMS.find((f) => f.id === form)!;
  const currency = currentForm.currency;

  // Bootstrap: load year list (fallback to current year).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const ys = await api.years();
        if (cancelled) return;
        const list = ys.length ? ys : [new Date().getFullYear()];
        setYears(list);
        setYear(list[0]);
      } catch (e: any) {
        if (!cancelled) {
          const fallback = [new Date().getFullYear()];
          setYears(fallback);
          setYear(fallback[0]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch the matching report whenever form or year changes.
  useEffect(() => {
    if (year == null) return;
    let cancelled = false;
    (async () => {
      setReportLoading(true);
      setReportError(null);
      setTax(null);
      setGst(null);
      try {
        if (form === "gst") {
          const r = await api.gstHst(year, "CAD");
          if (!cancelled) setGst(r);
        } else if (form === "t2125") {
          const r = await api.t2125(year, "CAD");
          if (!cancelled) setTax(r);
        } else {
          const r = await api.scheduleC(year, "USD");
          if (!cancelled) setTax(r);
        }
      } catch (e: any) {
        if (!cancelled) setReportError(e?.message || "Could not load this report");
      } finally {
        if (!cancelled) setReportLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [form, year]);

  // Three summary stats for the band.
  const stats = useMemo<{ value: string; label: string }[]>(() => {
    if (form === "gst") {
      if (!gst) return [];
      return [
        { value: fmt(gst.taxable_sales, "CAD"), label: "Taxable sales" },
        { value: fmt(gst.eligible_expenses, "CAD"), label: "Eligible expenses" },
        { value: `${gst.sales_count} / ${gst.expense_count}`, label: "Sales / expenses" },
      ];
    }
    if (!tax) return [];
    return [
      { value: fmt(tax.gross_income, currency), label: "Gross income" },
      { value: fmt(tax.total_expenses, currency), label: "Total expenses" },
      { value: fmt(tax.net_profit, currency), label: "Net profit" },
    ];
  }, [form, tax, gst, currency]);

  function buildCsv(): string {
    const esc = (v: string | number) => {
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const rows: (string | number)[][] = [];
    if (form === "gst" && gst) {
      rows.push(["section", "line", "total", "deductible", "count"]);
      rows.push(["sales", "Taxable sales", gst.taxable_sales, "", gst.sales_count]);
      rows.push(["expenses", "Eligible expenses", gst.eligible_expenses, "", gst.expense_count]);
    } else if (tax) {
      rows.push(["section", "line", "total", "deductible", "count"]);
      tax.income.forEach((l) => rows.push(["income", l.line, l.total, l.deductible, l.count]));
      tax.expenses.forEach((l) => rows.push(["expense", l.line, l.total, l.deductible, l.count]));
    }
    return rows.map((r) => r.map(esc).join(",")).join("\n");
  }

  function generateReport() {
    if (year == null) return;
    const csv = buildCsv();
    if (!csv) return;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ledger-${FILE_SLUG[form]}-${year}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const hasReport = form === "gst" ? !!gst : !!tax;

  return (
    <>
      <PageHeader title="Reports" subtitle="Generate and export financial summaries" />

      <div className="px-8 py-7 pb-16 lg-fade-up">
        <PageState loading={loading} error={error}>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.45fr_1fr]">
            {/* ── Left: Build a report ── */}
            <Card className="flex flex-col gap-[22px] p-6">
              <SectionTitle>Build a report</SectionTitle>

              {/* Form selector — segmented control */}
              <div className="flex flex-col gap-[10px]">
                <span className="text-[12.5px] font-semibold text-ink-700">Form</span>
                <div className="inline-flex w-fit flex-wrap gap-1 rounded-[11px] bg-surface-sunken p-1">
                  {FORMS.map((f) => {
                    const active = f.id === form;
                    return (
                      <button
                        key={f.id}
                        onClick={() => setForm(f.id)}
                        className={`rounded-lg px-3.5 py-2 text-[13px] font-semibold transition-colors ${
                          active
                            ? "bg-surface text-ink-900 shadow-hairline"
                            : "text-ink-600 hover:text-ink-900"
                        }`}
                      >
                        {f.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Year selector — pill chips */}
              <div className="flex flex-col gap-[10px]">
                <span className="text-[12.5px] font-semibold text-ink-700">Year</span>
                <div className="flex flex-wrap gap-2">
                  {years.map((y) => {
                    const active = y === year;
                    return (
                      <button
                        key={y}
                        onClick={() => setYear(y)}
                        className={`rounded-pill border px-3.5 py-2 text-[13px] font-medium transition-colors ${
                          active
                            ? "border-ink-900 bg-ink-900 text-white"
                            : "border-line-strong bg-surface text-ink-700 hover:bg-surface-sunken"
                        }`}
                      >
                        {y}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Summary band */}
              <div className="rounded-[14px] bg-surface-sunken p-[18px]">
                {reportLoading ? (
                  <div className="flex items-center gap-3 py-2 text-ink-400">
                    <Spinner /> <span className="text-sm">Loading summary…</span>
                  </div>
                ) : reportError ? (
                  <div className="py-1 text-sm text-ink-500">{reportError}</div>
                ) : stats.length ? (
                  <div className="flex items-center gap-[14px]">
                    {stats.map((s, i) => (
                      <div key={i} className="flex flex-1 items-center gap-[14px]">
                        {i > 0 && (
                          <div
                            className="h-[34px] w-px flex-none"
                            style={{ background: "var(--line-strong)" }}
                          />
                        )}
                        <div className="flex flex-1 flex-col gap-0.5">
                          <span className="font-mono text-[22px] font-bold text-ink-900">
                            {s.value}
                          </span>
                          <span className="text-[12px] text-ink-500">{s.label}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-1 text-sm text-ink-500">No data for this period.</div>
                )}
              </div>

              {/* Generate row */}
              <div className="flex items-center gap-[14px]">
                <span className="inline-flex items-center gap-[7px] text-[13px] text-ink-500">
                  <Icon name="calendar" size={15} />
                  {currentForm.label} · {year ?? "—"} · {currency}
                </span>
                <div className="ml-auto">
                  <Button onClick={generateReport} disabled={!hasReport || reportLoading}>
                    <Icon name="download" size={17} />
                    Generate report
                  </Button>
                </div>
              </div>
            </Card>

            {/* ── Right: Report breakdown ── */}
            <Card className="p-6">
              <SectionTitle>Report breakdown</SectionTitle>

              <div className="mt-4">
                {reportLoading ? (
                  <div className="flex items-center justify-center gap-3 py-16 text-ink-400">
                    <Spinner /> <span className="text-sm">Loading…</span>
                  </div>
                ) : reportError ? (
                  <EmptyState icon="info" title="Couldn't load report" body={reportError} />
                ) : form === "gst" ? (
                  gst ? (
                    <GstBreakdown gst={gst} />
                  ) : (
                    <EmptyState icon="file" title="Nothing to show" />
                  )
                ) : tax && (tax.expenses.length || tax.income.length) ? (
                  <div className="flex flex-col gap-6">
                    <LineTable
                      title="Expenses"
                      rows={tax.expenses}
                      currency={currency}
                      showDeductible
                    />
                    <LineTable
                      title="Income"
                      rows={tax.income}
                      currency={currency}
                      showDeductible={false}
                    />
                  </div>
                ) : (
                  <EmptyState
                    icon="file"
                    title="No lines to break down"
                    body="There are no categorized transactions for this form and year."
                  />
                )}
              </div>
            </Card>
          </div>
        </PageState>
      </div>
    </>
  );
}

function LineTable({
  title,
  rows,
  currency,
  showDeductible,
}: {
  title: string;
  rows: TaxLine[];
  currency: string;
  showDeductible: boolean;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[12.5px] font-semibold uppercase tracking-wide text-ink-500">
        {title}
      </span>
      <div className="overflow-hidden rounded-[12px] border border-line">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="bg-surface-sunken text-left text-[11px] uppercase tracking-wide text-ink-500">
              <th className="px-3.5 py-2.5 font-semibold">Line</th>
              <th className="px-3.5 py-2.5 text-right font-semibold">Count</th>
              <th className="px-3.5 py-2.5 text-right font-semibold">Total</th>
              {showDeductible && (
                <th className="px-3.5 py-2.5 text-right font-semibold">Deductible</th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={showDeductible ? 4 : 3}
                  className="px-3.5 py-6 text-center text-ink-400"
                >
                  None.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.line} className="border-t border-line">
                  <td className="px-3.5 py-2.5 text-ink-700">{r.line}</td>
                  <td className="px-3.5 py-2.5 text-right font-mono text-ink-500">
                    {r.count}
                  </td>
                  <td className="px-3.5 py-2.5 text-right font-mono text-ink-900">
                    {fmt(r.total, currency)}
                  </td>
                  {showDeductible && (
                    <td className="px-3.5 py-2.5 text-right font-mono font-semibold text-ink-700">
                      {fmt(r.deductible, currency)}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GstBreakdown({ gst }: { gst: GstHst }) {
  const rows = [
    { label: "Taxable sales", total: gst.taxable_sales, count: gst.sales_count },
    { label: "Eligible expenses", total: gst.eligible_expenses, count: gst.expense_count },
  ];
  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-hidden rounded-[12px] border border-line">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="bg-surface-sunken text-left text-[11px] uppercase tracking-wide text-ink-500">
              <th className="px-3.5 py-2.5 font-semibold">Line</th>
              <th className="px-3.5 py-2.5 text-right font-semibold">Count</th>
              <th className="px-3.5 py-2.5 text-right font-semibold">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-t border-line">
                <td className="px-3.5 py-2.5 text-ink-700">{r.label}</td>
                <td className="px-3.5 py-2.5 text-right font-mono text-ink-500">{r.count}</td>
                <td className="px-3.5 py-2.5 text-right font-mono text-ink-900">
                  {fmt(r.total, "CAD")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {gst.note && (
        <div className="rounded-[12px] border border-line bg-surface-sunken p-3.5 text-[12.5px] leading-relaxed text-ink-600">
          {gst.note}
        </div>
      )}
    </div>
  );
}
