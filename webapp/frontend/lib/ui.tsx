"use client";

import React from "react";

/* ============================================================
   Icons — a single inline-SVG set (stroke icons, currentColor)
   ============================================================ */
export const ICON_PATHS: Record<string, string> = {
  utensils:
    "M3 2v7c0 1.1.9 2 2 2s2-.9 2-2V2 M7 2v20 M21 15V2a5 5 0 0 0-3 5v6c0 1.1.9 2 2 2h1z M21 15v7",
  plane:
    "M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z",
  monitor: "M3 4h18v12H3z M8 21h8 M12 16v5",
  briefcase: "M4 7h16v13H4z M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2 M4 13h16",
  heart: "M19 14c1.4-1.4 3-3.1 3-5.4A4.6 4.6 0 0 0 12 5 4.6 4.6 0 0 0 2 8.6c0 2.3 1.6 4 3 5.4l7 7z",
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20 M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z",
  wallet: "M3 7h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h11v3 M18 12h.01",
  mail: "M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z M3 7l9 6 9-6",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 7v5l3 2",
  check: "M20 6 9 17l-5-5",
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z",
  bars: "M3 3v18h18 M7 16v-5 M12 16V8 M17 16v-9",
  list: "M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01",
  tag: "M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z M7 7h.01",
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h8",
  trending: "M16 7h6v6 M22 7l-8.5 8.5-5-5L2 17",
  bulb: "M9 18h6 M10 22h4 M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2z",
  chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  gear:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 13a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.3-4.3",
  bell: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9 M10.3 21a1.94 1.94 0 0 0 3.4 0",
  sparkle: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
  upload: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12",
  plus: "M12 5v14 M5 12h14",
  edit: "M12 20h9 M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z",
  trash: "M3 6h18 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M10 11v6 M14 11v6",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  arrowRight: "M5 12h14 M12 5l7 7-7 7",
  arrowLeft: "M19 12H5 M12 19l-7-7 7-7",
  info: "M12 16v-4 M12 8h.01 M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z",
  calendar: "M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  x: "M18 6 6 18 M6 6l12 12",
  send: "M22 2 11 13 M22 2l-7 20-4-9-9-4z",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  refresh: "M3 12a9 9 0 0 1 15-6.7L21 8 M21 3v5h-5 M21 12a9 9 0 0 1-15 6.7L3 16 M3 21v-5h5",
  zap: "M13 2 3 14h9l-1 8 10-12h-9z",
  scales: "M12 3v18 M5 7l-3 7h6z M19 7l-3 7h6z M5 21h14 M8 7h8",
  building: "M3 21h18 M6 21V7l6-4 6 4v14 M10 9h.01 M14 9h.01 M10 13h.01 M14 13h.01 M10 17h.01 M14 17h.01",
};

export type IconName = keyof typeof ICON_PATHS;

export function Icon({
  name,
  size = 18,
  strokeWidth = 2,
  className,
  style,
}: {
  name: IconName | string;
  size?: number;
  strokeWidth?: number;
  className?: string;
  style?: React.CSSProperties;
}) {
  const d = ICON_PATHS[name] || ICON_PATHS.tag;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
    >
      {d.split(" M").map((seg, i) => (
        <path key={i} d={i === 0 ? seg : `M${seg}`} />
      ))}
    </svg>
  );
}

/* ============================================================
   Accents — category color spectrum
   ============================================================ */
export type Accent = "violet" | "coral" | "teal" | "amber" | "sky" | "lime";
export const ACCENTS: Accent[] = ["violet", "coral", "teal", "amber", "sky", "lime"];

export const accent = (a: Accent | string) => `var(--${a}-600)`;
export const accentTint = (a: Accent | string) => `var(--${a}-100)`;
export const accentWash = (a: Accent | string) => `var(--${a}-50)`;
export const accentBright = (a: Accent | string) => `var(--${a}-500)`;

/** Map a free-form backend category to a design accent + icon. */
export function categoryStyle(category?: string): { accent: Accent; icon: IconName } {
  const c = (category || "").toLowerCase();
  const has = (...keys: string[]) => keys.some((k) => c.includes(k));
  if (has("food", "meal", "dining", "restaurant", "grocer", "coffee", "cafe")) return { accent: "coral", icon: "utensils" };
  if (has("travel", "flight", "air", "hotel", "uber", "lyft", "transit", "rail", "lodging", "car rental")) return { accent: "sky", icon: "plane" };
  if (has("software", "saas", "subscription", "app", "hosting", "domain", "cloud", "web", "digital")) return { accent: "violet", icon: "monitor" };
  if (has("office", "supplies", "equipment", "hardware", "shipping", "postage")) return { accent: "amber", icon: "briefcase" };
  if (has("health", "wellness", "pharmacy", "gym", "medical", "fitness", "dental")) return { accent: "teal", icon: "heart" };
  if (has("education", "course", "learning", "book", "training", "tuition")) return { accent: "lime", icon: "book" };
  if (has("income", "revenue", "sales", "payout", "deposit")) return { accent: "teal", icon: "trending" };
  if (has("util", "phone", "internet", "electric", "rent", "insurance")) return { accent: "sky", icon: "building" };
  return { accent: "violet", icon: "wallet" };
}

/** Hash any string to a stable accent (for vendors/symbols without a category). */
export function accentFor(seed: string): Accent {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return ACCENTS[h % ACCENTS.length];
}

/* ============================================================
   Core components
   ============================================================ */
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "soft" | "danger";
  size?: "sm" | "md" | "lg";
  block?: boolean;
};

export function Button({
  variant = "primary",
  size = "md",
  block,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  const sizes: Record<string, string> = {
    sm: "h-9 px-3.5 text-[13px] rounded-sm",
    md: "h-11 px-4 text-sm rounded-sm",
    lg: "h-[52px] px-6 text-[15px] rounded-md",
  };
  const variants: Record<string, string> = {
    primary:
      "bg-violet-600 text-white shadow-brand hover:bg-violet-700 disabled:opacity-50",
    secondary:
      "bg-surface text-ink-800 border border-line-strong hover:bg-surface-sunken disabled:opacity-50",
    ghost: "bg-transparent text-ink-700 hover:bg-surface-sunken",
    soft: "bg-violet-50 text-violet-700 hover:bg-violet-100",
    danger:
      "bg-danger-100 text-danger-600 hover:bg-danger-500 hover:text-white",
  };
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 font-semibold font-body transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed ${sizes[size]} ${variants[variant]} ${block ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Card({
  className = "",
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`bg-surface border border-line rounded-lg shadow-hairline ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function BentoTile({
  accent: a = "violet",
  icon,
  children,
  className = "",
}: {
  accent?: Accent;
  icon?: IconName;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col rounded-lg p-5 border ${className}`}
      style={{
        background: accentWash(a),
        borderColor: accentTint(a),
        minHeight: 138,
      }}
    >
      {icon && (
        <span
          className="flex h-9 w-9 items-center justify-center rounded-[11px] bg-white"
          style={{ color: accent(a), boxShadow: "var(--shadow-xs)" }}
        >
          <Icon name={icon} size={18} />
        </span>
      )}
      {children}
    </div>
  );
}

export function StatusPill({
  tone,
  children,
}: {
  tone: "success" | "warning" | "danger" | "info" | "neutral";
  children: React.ReactNode;
}) {
  const tones: Record<string, { bg: string; fg: string; dot: string }> = {
    success: { bg: "var(--success-100)", fg: "var(--success-600)", dot: "var(--success-500)" },
    warning: { bg: "var(--amber-100)", fg: "var(--amber-700)", dot: "var(--amber-500)" },
    danger: { bg: "var(--danger-100)", fg: "var(--danger-600)", dot: "var(--danger-500)" },
    info: { bg: "var(--violet-50)", fg: "var(--violet-700)", dot: "var(--violet-500)" },
    neutral: { bg: "var(--surface-sunken)", fg: "var(--ink-600)", dot: "var(--ink-400)" },
  };
  const t = tones[tone];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-xs font-semibold"
      style={{ background: t.bg, color: t.fg }}
    >
      <span className="h-1.5 w-1.5 rounded-pill" style={{ background: t.dot }} />
      {children}
    </span>
  );
}

export function Chip({
  active,
  icon,
  onClick,
  children,
}: {
  active?: boolean;
  icon?: IconName;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-pill border px-3.5 py-2 text-[13px] font-medium transition-colors ${
        active
          ? "border-ink-900 bg-ink-900 text-white"
          : "border-line-strong bg-surface text-ink-700 hover:bg-surface-sunken"
      }`}
    >
      {icon && <Icon name={icon} size={15} />}
      {children}
    </button>
  );
}

export function Spinner({ size = 18, light = false }: { size?: number; light?: boolean }) {
  return (
    <span
      className="inline-block rounded-pill"
      style={{
        width: size,
        height: size,
        border: `2px solid ${light ? "rgba(255,255,255,.35)" : "var(--line-strong)"}`,
        borderTopColor: light ? "#fff" : "var(--violet-600)",
        animation: "lg-spin .7s linear infinite",
      }}
    />
  );
}

export function EmptyState({
  icon = "search",
  title,
  body,
  action,
}: {
  icon?: IconName;
  title: string;
  body?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3.5 px-5 py-16 text-center">
      <div
        className="flex h-16 w-16 items-center justify-center rounded-[20px]"
        style={{ background: "var(--violet-50)", color: "var(--violet-500)" }}
      >
        <Icon name={icon} size={30} />
      </div>
      <div className="font-display text-lg font-semibold text-ink-900">{title}</div>
      {body && <div className="max-w-xs text-sm leading-relaxed text-ink-500">{body}</div>}
      {action}
    </div>
  );
}

/** Loading / error wrapper for data-fetching pages. */
export function PageState({
  loading,
  error,
  children,
}: {
  loading?: boolean;
  error?: string | null;
  children: React.ReactNode;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-ink-400">
        <Spinner /> <span className="text-sm">Loading…</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="py-20">
        <EmptyState icon="info" title="Something went wrong" body={error} />
      </div>
    );
  }
  return <>{children}</>;
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <span className="font-display text-[17px] font-bold text-ink-900">{children}</span>;
}
