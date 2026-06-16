"use client";

const LABELS: Record<string, string> = {
  USD: "🇺🇸 USD",
  CAD: "🇨🇦 CAD",
};

export default function CurrencyPicker({
  currencies,
  value,
  onChange,
}: {
  currencies: string[];
  value: string;
  onChange: (currency: string) => void;
}) {
  if (currencies.length <= 1) return null;
  return (
    <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5 shadow-sm">
      {currencies.map((c) => (
        <button
          key={c}
          onClick={() => onChange(c)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            value === c
              ? "bg-ink text-white"
              : "text-slate-500 hover:text-ink"
          }`}
        >
          {LABELS[c] ?? c}
        </button>
      ))}
    </div>
  );
}
