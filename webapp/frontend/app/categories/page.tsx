"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Icon,
  Button,
  Card,
  Spinner,
  PageState,
  EmptyState,
  categoryStyle,
  accent,
  accentTint,
  accentWash,
  type Accent,
} from "@/lib/ui";
import { PageHeader } from "@/components/PageHeader";
import { api, fmt, type Overview, type Budget } from "@/lib/api";

export default function CategoriesPage() {
  const year = new Date().getFullYear();
  const currency = "USD";

  const [overview, setOverview] = useState<Overview | null>(null);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [ov, bs] = await Promise.all([api.overview(year, currency), api.budgets()]);
      setOverview(ov);
      setBudgets(bs);
    } catch (e: any) {
      setError(e?.message || "Failed to load categories");
    } finally {
      setLoading(false);
    }
  }

  async function refreshBudgets() {
    try {
      setBudgets(await api.budgets());
    } catch {
      /* surfaced by next full load */
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Merge actual spend (by_category) with the matching budget (name + currency).
  const cards = useMemo(() => {
    const cats = overview?.by_category ?? [];
    return cats.map((c) => {
      const budget = budgets.find(
        (b) => b.category === c.name && b.currency === currency
      );
      return {
        name: c.name,
        total: c.total,
        count: c.count,
        limit: budget?.monthly_limit ?? null,
      };
    });
  }, [overview, budgets, currency]);

  return (
    <>
      <PageHeader title="Categories" subtitle="Spending against your monthly budgets" />
      <div className="px-8 py-7 pb-16 lg-fade-up">
        <PageState loading={loading} error={error}>
          {cards.length === 0 ? (
            <EmptyState
              icon="tag"
              title="No categories yet"
              body="Scan your inbox and Ledger will sort expenses into categories automatically."
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
              {cards.map((c) => (
                <CategoryCard
                  key={c.name}
                  name={c.name}
                  total={c.total}
                  count={c.count}
                  limit={c.limit}
                  currency={currency}
                  onSaved={refreshBudgets}
                />
              ))}
              <AddCategoryTile currency={currency} onSaved={refreshBudgets} />
            </div>
          )}
        </PageState>
      </div>
    </>
  );
}

function CategoryCard({
  name,
  total,
  count,
  limit,
  currency,
  onSaved,
}: {
  name: string;
  total: number;
  count: number;
  limit: number | null;
  currency: string;
  onSaved: () => void | Promise<void>;
}) {
  const { accent: a, icon } = categoryStyle(name);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(limit != null ? String(limit) : "");
  const [saving, setSaving] = useState(false);

  const pct = limit && limit > 0 ? Math.round((total / limit) * 100) : null;
  const over = limit != null && total > limit;
  const fillPct = limit && limit > 0 ? Math.min((total / limit) * 100, 100) : 0;

  async function save() {
    const num = parseFloat(value);
    if (Number.isNaN(num)) return;
    setSaving(true);
    try {
      await api.setBudget(name, num, currency);
      await onSaved();
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    setValue(limit != null ? String(limit) : "");
    setEditing(false);
  }

  return (
    <Card className="p-5 flex flex-col gap-4">
      {/* Header row */}
      <div className="flex items-center gap-3">
        <span
          className="flex h-[42px] w-[42px] flex-none items-center justify-center rounded-xl"
          style={{ background: accentTint(a as Accent), color: accent(a as Accent) }}
        >
          <Icon name={icon} size={20} />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-px">
          <span className="truncate font-display text-[15.5px] font-semibold text-ink-900">
            {name}
          </span>
          <span className="text-xs text-ink-500">{count} receipts</span>
        </div>
        <button
          aria-label="Edit budget"
          onClick={() => setEditing((v) => !v)}
          className="flex h-8 w-8 flex-none items-center justify-center rounded-[9px] border border-line-strong bg-surface text-ink-500 hover:bg-surface-sunken"
        >
          <Icon name="edit" size={15} />
        </button>
      </div>

      {/* Body */}
      <div>
        <div className="mb-2 flex items-baseline justify-between">
          <span className="font-mono text-[18px] font-bold text-ink-900">{fmt(total, currency)}</span>
          <span className="text-[12.5px] text-ink-500">
            of {limit != null ? fmt(limit, currency) : "—"}
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-pill bg-surface-sunken">
          <div
            className="h-full rounded-pill transition-all"
            style={{
              width: `${fillPct}%`,
              background: over ? "var(--danger-500)" : accent(a as Accent),
            }}
          />
        </div>
        <div className="mt-[7px] text-xs text-ink-500">
          {limit != null ? `${pct}% of monthly budget used` : "No budget set"}
        </div>
      </div>

      {/* Inline budget editor */}
      {editing && (
        <div className="flex items-center gap-2 border-t border-line pt-3">
          <input
            type="number"
            min={0}
            step="any"
            value={value}
            autoFocus
            onChange={(e) => setValue(e.target.value)}
            placeholder="Monthly limit"
            className="h-9 min-w-0 flex-1 rounded-sm border border-line-strong bg-surface px-3 font-body text-sm text-ink-900 outline-none placeholder:text-ink-400 focus:border-violet-500"
          />
          <Button size="sm" onClick={save} disabled={saving}>
            {saving ? <Spinner size={14} light /> : "Save"}
          </Button>
          <Button size="sm" variant="ghost" onClick={cancel} disabled={saving}>
            Cancel
          </Button>
        </div>
      )}
    </Card>
  );
}

function AddCategoryTile({
  currency,
  onSaved,
}: {
  currency: string;
  onSaved: () => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState("");
  const [limit, setLimit] = useState("");
  const [saving, setSaving] = useState(false);

  async function save() {
    const num = parseFloat(limit);
    if (!category.trim() || Number.isNaN(num)) return;
    setSaving(true);
    try {
      await api.setBudget(category.trim(), num, currency);
      await onSaved();
      setCategory("");
      setLimit("");
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="group flex min-h-[160px] flex-col items-center justify-center gap-2.5 rounded-lg border-[1.5px] border-dashed border-line-strong p-5 text-ink-500 transition-colors hover:border-violet-500 hover:text-violet-600"
      >
        <span
          className="flex h-[42px] w-[42px] items-center justify-center rounded-xl"
          style={{ background: "var(--violet-50)", color: "var(--violet-600)" }}
        >
          <Icon name="plus" size={20} />
        </span>
        <span className="text-sm font-semibold">Add a category</span>
      </button>
    );
  }

  return (
    <Card className="flex min-h-[160px] flex-col gap-3 p-5">
      <span className="font-display text-[15.5px] font-semibold text-ink-900">Set a budget</span>
      <input
        type="text"
        value={category}
        autoFocus
        onChange={(e) => setCategory(e.target.value)}
        placeholder="Category name"
        className="h-9 rounded-sm border border-line-strong bg-surface px-3 font-body text-sm text-ink-900 outline-none placeholder:text-ink-400 focus:border-violet-500"
      />
      <input
        type="number"
        min={0}
        step="any"
        value={limit}
        onChange={(e) => setLimit(e.target.value)}
        placeholder="Monthly limit"
        className="h-9 rounded-sm border border-line-strong bg-surface px-3 font-body text-sm text-ink-900 outline-none placeholder:text-ink-400 focus:border-violet-500"
      />
      <div className="mt-auto flex items-center gap-2">
        <Button size="sm" block onClick={save} disabled={saving}>
          {saving ? <Spinner size={14} light /> : "Save"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setOpen(false);
            setCategory("");
            setLimit("");
          }}
          disabled={saving}
        >
          Cancel
        </Button>
      </div>
    </Card>
  );
}
