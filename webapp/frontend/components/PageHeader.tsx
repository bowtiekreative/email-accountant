"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button, Icon } from "@/lib/ui";

export function PageHeader({
  title,
  subtitle,
  children,
  showScan = false,
  onScanned,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
  showScan?: boolean;
  onScanned?: () => void;
}) {
  return (
    <header
      className="sticky top-0 z-20 flex flex-none items-center gap-[18px] border-b border-line px-8 py-[18px]"
      style={{ background: "rgba(255,255,255,.78)", backdropFilter: "blur(12px)" }}
    >
      <div className="mr-auto flex min-w-0 flex-col gap-[3px]">
        <h1 className="font-display text-[23px] font-bold tracking-[-0.02em] text-ink-900">{title}</h1>
        {subtitle && <span className="text-[13px] text-ink-500">{subtitle}</span>}
      </div>
      {children}
      <button
        aria-label="Notifications"
        className="relative flex h-[42px] w-[42px] flex-none items-center justify-center rounded-md border border-line-strong bg-surface text-ink-700 hover:bg-surface-sunken"
      >
        <Icon name="bell" size={19} />
        <span
          className="absolute right-2.5 top-2.5 h-[7px] w-[7px] rounded-pill"
          style={{ background: "var(--coral-500)", border: "2px solid var(--surface)" }}
        />
      </button>
      {showScan && <ScanButton onScanned={onScanned} />}
    </header>
  );
}

export function ScanButton({ onScanned }: { onScanned?: () => void }) {
  const [busy, setBusy] = useState(false);
  async function scan() {
    setBusy(true);
    try {
      await api.startScan("incremental");
      onScanned?.();
    } catch {
      /* surfaced elsewhere */
    } finally {
      setTimeout(() => setBusy(false), 1200);
    }
  }
  return (
    <Button onClick={scan} disabled={busy}>
      <Icon name="sparkle" size={17} />
      {busy ? "Scanning…" : "Scan inbox"}
    </Button>
  );
}

/** Inline search field matching the design header search. */
export function HeaderSearch({
  value,
  onChange,
  placeholder = "Search vendor or category",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="flex h-[42px] w-[248px] items-center gap-2.5 rounded-md border border-line-strong bg-surface px-3.5">
      <Icon name="search" size={17} style={{ color: "var(--ink-300)" }} />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="min-w-0 flex-1 border-none bg-transparent font-body text-sm text-ink-900 outline-none placeholder:text-ink-400"
      />
    </div>
  );
}
