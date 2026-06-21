"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Icon,
  Button,
  Card,
  StatusPill,
  Spinner,
  PageState,
  categoryStyle,
  accent,
  accentTint,
  type Accent,
} from "@/lib/ui";
import { PageHeader } from "@/components/PageHeader";
import { api, fmt, type TransactionDetail, type TransactionPatch } from "@/lib/api";

const CURRENCY = "USD";

// Common category presets for the chooser (label → categoryStyle accent/icon).
const CATEGORY_CHOICES = [
  "Food & dining",
  "Travel",
  "Software",
  "Office",
  "Health",
  "Learning",
];

const fmtDate = (s?: string) => {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d.getTime())) return s.slice(0, 10);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

// Pull just the currency symbol out of an Intl-formatted amount, e.g. "$", "CA$".
const currencySymbol = (currency = CURRENCY) =>
  fmt(0, currency).replace(/[\d.,\s]/g, "") || "$";

export default function TransactionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const rawId = Array.isArray(params.id) ? params.id[0] : (params.id as string);
  const id = decodeURIComponent(rawId || "");

  const [data, setData] = useState<TransactionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Local editable state (controlled inputs).
  const [vendor, setVendor] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [category, setCategory] = useState("");

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [verifying, setVerifying] = useState(false);

  function hydrate(d: TransactionDetail) {
    const t = d.transaction;
    setVendor(t.merchant_name || "");
    setAmount(t.amount != null ? String(t.amount) : "");
    setDate(t.email_date || "");
    setCategory(t.category || "");
  }

  function load() {
    setData(null);
    setError(null);
    api
      .transactionDetail(id)
      .then((d) => {
        setData(d);
        hydrate(d);
      })
      .catch((e) => setError(e?.message || "Failed to load receipt"));
  }

  useEffect(() => {
    if (id) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const tx = data?.transaction;
  const currency = tx?.currency || CURRENCY;
  const cs = categoryStyle(category || tx?.category);
  const reviewed = !!tx?.reviewed;

  const confidenceLabel = useMemo(() => {
    const c = tx?.classification_confidence;
    const pct = c != null ? Math.round(c * 100) : 0;
    return pct ? `${pct}% confident` : "— confident";
  }, [tx?.classification_confidence]);

  async function save() {
    setSaving(true);
    setSaved(false);
    try {
      const patch: TransactionPatch = {
        merchant_name: vendor || undefined,
        category: category || undefined,
      };
      const num = parseFloat(amount);
      if (!isNaN(num)) patch.amount = num;
      await api.updateTransaction(id, patch);
      setSaved(true);
      setTimeout(() => setSaved(false), 2400);
      load();
    } catch (e: any) {
      setError(e?.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function markVerified() {
    setVerifying(true);
    try {
      await api.updateTransaction(id, { reviewed: true, needs_review: false });
      load();
    } catch (e: any) {
      setError(e?.message || "Verify failed");
    } finally {
      setVerifying(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      await api.deleteTransactions([id]);
      router.push("/transactions");
    } catch (e: any) {
      setError(e?.message || "Delete failed");
      setDeleting(false);
    }
  }

  // Meta rows for "Payment & record" — only those with a value.
  const metaRows: { k: string; v?: string | null; mono?: boolean }[] = [
    { k: "Category", v: tx?.category },
    { k: "Tax category", v: tx?.tax_category },
    { k: "Type", v: tx?.transaction_type },
    { k: "Domain", v: tx?.domain },
    { k: "Account", v: tx?.account, mono: true },
    { k: "Currency", v: tx?.currency },
  ];

  const email = data?.email;
  const attachments = data?.attachments || [];

  return (
    <>
      <PageHeader title="Receipt details" subtitle="Review and confirm what Ledger extracted." />

      <div className="px-8 py-7 pb-16 lg-fade-up">
        <div className="max-w-[1000px] mx-auto">
          <PageState loading={data === null && !error} error={error}>
            {tx && (
              <>
                {/* Toolbar */}
                <div className="mb-[22px] flex flex-wrap items-center gap-[14px]">
                  <Button variant="secondary" onClick={() => router.back()}>
                    <Icon name="arrowLeft" size={17} />
                    Back
                  </Button>
                  <span className="font-mono text-[13px] text-ink-400">{id}</span>
                  <div className="ml-auto flex items-center gap-2.5">
                    <Button variant="danger" onClick={remove} disabled={deleting}>
                      {deleting ? <Spinner size={16} /> : <Icon name="trash" size={17} />}
                      Delete
                    </Button>
                    {reviewed ? (
                      <StatusPill tone="success">Verified</StatusPill>
                    ) : (
                      <Button onClick={markVerified} disabled={verifying}>
                        {verifying ? <Spinner size={16} light /> : <Icon name="check" size={17} />}
                        Mark verified
                      </Button>
                    )}
                  </div>
                </div>

                {/* Two-column grid */}
                <div className="grid items-start gap-5 grid-cols-1 lg:[grid-template-columns:1fr_1.15fr]">
                  {/* LEFT */}
                  <div className="flex flex-col gap-[18px]">
                    {/* Sunken panel with paper receipt */}
                    <div className="relative flex items-center justify-center rounded-lg bg-surface-sunken p-7">
                      {/* Category chip top-left */}
                      <div
                        className="absolute left-3.5 top-3.5 inline-flex items-center gap-[7px] rounded-pill bg-white py-[5px] pl-2 pr-[11px] text-[12px] font-semibold shadow-hairline"
                        style={{ color: accent(cs.accent) }}
                      >
                        <Icon name={cs.icon} size={14} />
                        {category || tx.category || "Uncategorized"}
                      </div>
                      {/* Status chip top-right */}
                      <div className="absolute right-3.5 top-3.5">
                        {reviewed ? (
                          <StatusPill tone="success">Verified</StatusPill>
                        ) : (
                          <StatusPill tone="warning">Pending</StatusPill>
                        )}
                      </div>

                      {/* Paper receipt mock */}
                      <div
                        className="w-full max-w-[240px] rounded-t-xl bg-white"
                        style={{ boxShadow: "0 12px 30px -12px rgba(27,26,34,.28)" }}
                      >
                        <div
                          className="h-[5px] rounded-t-xl"
                          style={{ background: accent(cs.accent) }}
                        />
                        <div className="px-[22px] pb-1.5 pt-5">
                          <div className="text-center font-mono text-sm font-bold uppercase tracking-[.04em] text-ink-900">
                            {vendor || tx.merchant_name || "Unknown vendor"}
                          </div>
                          <div className="mt-1 text-center text-[11px] text-ink-500">
                            {fmtDate(date || tx.email_date)}
                          </div>
                          <div
                            className="my-3.5 h-px"
                            style={{
                              background:
                                "repeating-linear-gradient(90deg,var(--line-strong) 0 4px,transparent 4px 8px)",
                            }}
                          />
                          <div className="flex flex-col gap-2.5">
                            {[
                              ["52%", "20%"],
                              ["38%", "16%"],
                              ["44%", "18%"],
                            ].map(([w1, w2], i) => (
                              <div key={i} className="flex justify-between gap-2.5">
                                <span
                                  className="h-[7px] rounded-pill"
                                  style={{ width: w1, background: "var(--line-strong)" }}
                                />
                                <span
                                  className="h-[7px] rounded-pill"
                                  style={{ width: w2, background: "#e6e0d4" }}
                                />
                              </div>
                            ))}
                          </div>
                          <div
                            className="my-3.5 h-px"
                            style={{
                              background:
                                "repeating-linear-gradient(90deg,var(--line-strong) 0 4px,transparent 4px 8px)",
                            }}
                          />
                          <div className="flex items-baseline justify-between">
                            <span className="font-mono text-[11px] font-bold tracking-[.12em] text-ink-500">
                              TOTAL
                            </span>
                            <span className="font-mono text-[19px] font-bold text-ink-900">
                              {fmt(tx.amount, currency)}
                            </span>
                          </div>
                        </div>
                        {/* Zig-zag bottom edge */}
                        <div
                          className="h-3 bg-white"
                          style={{
                            WebkitMaskImage:
                              "linear-gradient(45deg,#000 50%,transparent 51%),linear-gradient(-45deg,#000 50%,transparent 51%)",
                            WebkitMaskSize: "14px 14px",
                            WebkitMaskRepeat: "repeat-x",
                            WebkitMaskPosition: "bottom",
                            maskImage:
                              "linear-gradient(45deg,#000 50%,transparent 51%),linear-gradient(-45deg,#000 50%,transparent 51%)",
                            maskSize: "14px 14px",
                            maskRepeat: "repeat-x",
                            maskPosition: "bottom",
                          }}
                        />
                      </div>
                    </div>

                    {/* Source email card */}
                    <Card className="flex flex-col gap-[11px] p-5">
                      <div className="flex items-center gap-2 text-ink-600">
                        <Icon name="mail" size={16} />
                        <span className="text-[12.5px] font-semibold">Source email</span>
                      </div>
                      {email ? (
                        <>
                          {email.subject && (
                            <div className="text-[13.5px] font-semibold text-ink-900">
                              {email.subject}
                            </div>
                          )}
                          {(email.from || email.sender || email.from_address) && (
                            <div className="text-[12.5px] text-ink-500">
                              {email.from || email.sender || email.from_address}
                            </div>
                          )}
                          {(email.snippet || email.body_preview || email.preview) && (
                            <p className="m-0 text-[13px] leading-relaxed text-ink-600">
                              {email.snippet || email.body_preview || email.preview}
                            </p>
                          )}
                        </>
                      ) : (
                        <p className="m-0 text-[13px] leading-relaxed text-ink-500">
                          No source email on file.
                        </p>
                      )}
                    </Card>
                  </div>

                  {/* RIGHT */}
                  <div className="flex flex-col gap-[18px]">
                    {/* Extracted details */}
                    <Card className="flex flex-col gap-4 p-[22px]">
                      <div className="flex items-center justify-between">
                        <span className="font-display text-base font-bold text-ink-900">
                          Extracted details
                        </span>
                        <StatusPill tone="info">
                          <Icon name="sparkle" size={13} />
                          {confidenceLabel}
                        </StatusPill>
                      </div>

                      {/* Vendor */}
                      <label className="flex flex-col gap-[7px]">
                        <span className="text-[12.5px] font-semibold text-ink-700">Vendor</span>
                        <input
                          value={vendor}
                          onChange={(e) => setVendor(e.target.value)}
                          className="rounded-xl border-[1.5px] border-line-strong bg-surface px-[13px] py-[11px] font-body text-[15px] text-ink-900 outline-none focus:border-violet-500"
                        />
                      </label>

                      {/* Amount + Date */}
                      <div className="flex gap-3">
                        <label className="flex flex-1 flex-col gap-[7px]">
                          <span className="text-[12.5px] font-semibold text-ink-700">Amount</span>
                          <div className="flex items-center rounded-xl border-[1.5px] border-line-strong bg-surface px-[13px] focus-within:border-violet-500">
                            <span className="mr-1.5 font-mono text-[15px] text-ink-500">
                              {currencySymbol(currency)}
                            </span>
                            <input
                              value={amount}
                              onChange={(e) => setAmount(e.target.value)}
                              inputMode="decimal"
                              className="min-w-0 flex-1 border-none bg-transparent py-[11px] font-mono text-[15px] font-semibold text-ink-900 outline-none"
                            />
                          </div>
                        </label>
                        <label className="flex flex-1 flex-col gap-[7px]">
                          <span className="text-[12.5px] font-semibold text-ink-700">Date</span>
                          <input
                            value={date}
                            onChange={(e) => setDate(e.target.value)}
                            className="rounded-xl border-[1.5px] border-line-strong bg-surface px-[13px] py-[11px] font-body text-[15px] text-ink-900 outline-none focus:border-violet-500"
                          />
                        </label>
                      </div>

                      {/* Category chooser */}
                      <div className="flex flex-col gap-[9px]">
                        <span className="text-[12.5px] font-semibold text-ink-700">Category</span>
                        <div className="flex flex-wrap gap-2">
                          {CATEGORY_CHOICES.map((label) => {
                            const ccs = categoryStyle(label);
                            const active = category === label;
                            return (
                              <button
                                key={label}
                                type="button"
                                onClick={() => setCategory(label)}
                                className="inline-flex items-center gap-2 rounded-pill border-[1.5px] px-3.5 py-2 text-[13px] font-medium transition-colors"
                                style={
                                  active
                                    ? {
                                        borderColor: accent(ccs.accent as Accent),
                                        background: accentTint(ccs.accent as Accent),
                                        color: accent(ccs.accent as Accent),
                                      }
                                    : {
                                        borderColor: "var(--line-strong)",
                                        background: "var(--surface)",
                                        color: "var(--ink-700)",
                                      }
                                }
                              >
                                <Icon name={ccs.icon} size={15} />
                                {label}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Save */}
                      <div className="flex items-center gap-3 pt-1">
                        <Button onClick={save} disabled={saving}>
                          {saving ? <Spinner size={16} light /> : <Icon name="check" size={17} />}
                          Save changes
                        </Button>
                        {saved && (
                          <span className="text-[13px] font-semibold text-success-600">
                            Saved.
                          </span>
                        )}
                      </div>
                    </Card>

                    {/* Payment & record */}
                    <Card className="flex flex-col gap-0.5 p-[22px]">
                      <span className="mb-2 font-display text-base font-bold text-ink-900">
                        Payment &amp; record
                      </span>
                      {metaRows
                        .filter((r) => r.v != null && r.v !== "")
                        .map((r) => (
                          <div
                            key={r.k}
                            className="flex items-center justify-between border-b border-line-faint py-2.5"
                          >
                            <span className="text-[13px] text-ink-500">{r.k}</span>
                            <span
                              className={`text-[13.5px] font-medium text-ink-800 ${
                                r.mono ? "font-mono" : ""
                              }`}
                            >
                              {r.v}
                            </span>
                          </div>
                        ))}
                    </Card>

                    {/* Attachments */}
                    {attachments.length > 0 && (
                      <Card className="flex flex-col gap-3 p-[22px]">
                        <span className="font-display text-base font-bold text-ink-900">
                          Attachments
                        </span>
                        <div className="flex flex-col gap-2.5">
                          {attachments.map((a, i) => (
                            <div key={`${a.filename}-${i}`} className="flex flex-col gap-2">
                              <div className="flex items-center gap-2.5 text-ink-700">
                                <span className="flex h-8 w-8 flex-none items-center justify-center rounded-[9px] bg-surface-sunken text-ink-500">
                                  <Icon name="file" size={16} />
                                </span>
                                <span className="truncate text-[13.5px] font-medium text-ink-800">
                                  {a.filename}
                                </span>
                              </div>
                              {a.ocr_text && (
                                <details className="rounded-md border border-line bg-surface-sunken px-3 py-2">
                                  <summary className="cursor-pointer text-[12.5px] font-semibold text-ink-600">
                                    View extracted text
                                  </summary>
                                  <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-ink-700">
                                    {a.ocr_text}
                                  </pre>
                                </details>
                              )}
                            </div>
                          ))}
                        </div>
                      </Card>
                    )}
                  </div>
                </div>
              </>
            )}
          </PageState>
        </div>
      </div>
    </>
  );
}
