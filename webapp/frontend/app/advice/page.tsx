"use client";

import { useEffect, useState } from "react";
import {
  api,
  fmt,
  type Reminder,
  type WealthAdvice,
} from "@/lib/api";
import {
  Card,
  EmptyState,
  Icon,
  PageState,
  accent,
  accentTint,
  type Accent,
  type IconName,
} from "@/lib/ui";
import { PageHeader } from "@/components/PageHeader";

const CURRENCY = "USD";

type AdviceCard = {
  key: string;
  accent: Accent;
  icon: IconName;
  tag: string;
  title: string;
  body: string;
};

/** Map a severity / reminder level to a design accent + icon. */
function severityStyle(severity?: string): { accent: Accent; icon: IconName } {
  const s = (severity || "").toLowerCase();
  if (s === "high") return { accent: "coral", icon: "zap" };
  if (s === "medium") return { accent: "amber", icon: "bulb" };
  if (s === "low") return { accent: "teal", icon: "info" };
  return { accent: "violet", icon: "info" };
}

function severityLabel(severity?: string): string {
  const s = (severity || "").toLowerCase();
  if (s === "high") return "Priority";
  if (s === "medium") return "Worth a look";
  if (s === "low") return "Tip";
  return "Tip";
}

function TagPill({ accent: a, children }: { accent: Accent; children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center rounded-pill px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide"
      style={{ background: accentTint(a), color: accent(a) }}
    >
      {children}
    </span>
  );
}

export default function AdvicePage() {
  const [advice, setAdvice] = useState<WealthAdvice | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      api.wealthAdvice(CURRENCY),
      api.reminders(CURRENCY).catch(() => [] as Reminder[]),
    ])
      .then(([a, r]) => {
        if (cancelled) return;
        setAdvice(a);
        setReminders(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Could not load advice");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const cf = advice?.cashflow;
  const freeable =
    (cf?.monthly_surplus ?? 0) + (advice?.inactive_subscription_monthly ?? 0);
  const hasFreeable = freeable > 0;

  const cards: AdviceCard[] = [];
  advice?.tips?.forEach((t, i) => {
    const st = severityStyle(t.severity);
    cards.push({
      key: `tip-${i}`,
      accent: st.accent,
      icon: st.icon,
      tag: severityLabel(t.severity),
      title: t.title,
      body: t.body,
    });
  });
  reminders.forEach((r, i) => {
    const st = severityStyle(r.severity);
    cards.push({
      key: `rem-${i}`,
      accent: st.accent,
      icon: "bell",
      tag: r.type ? r.type.replace(/_/g, " ") : severityLabel(r.severity),
      title: severityLabel(r.severity) === "Priority" ? "Needs attention" : "Reminder",
      body: r.message,
    });
  });

  const principles = advice?.principles ?? [];

  return (
    <>
      <PageHeader
        title="Smart advice"
        subtitle="Personalized ways to save and stay on track"
      />
      <div className="px-8 py-7 pb-16 lg-fade-up">
        <PageState loading={loading} error={error}>
          {cards.length === 0 ? (
            <EmptyState
              icon="bulb"
              title="No advice yet"
              body="Once Ledger has a bit more spending history, you'll see calm, specific ways to save here."
            />
          ) : (
            <div className="flex flex-col gap-[22px]">
              {/* Hero banner */}
              <div
                className="flex items-center gap-[18px] rounded-[20px] p-[24px_28px] text-white"
                style={{
                  background:
                    "linear-gradient(135deg,var(--violet-600),var(--violet-700))",
                }}
              >
                <div
                  className="flex h-[52px] w-[52px] flex-none items-center justify-center rounded-[14px]"
                  style={{ background: "rgba(255,255,255,.18)" }}
                >
                  <Icon name="bulb" size={26} />
                </div>
                <div className="flex-1">
                  <div className="mb-[3px] font-display text-[19px] font-bold">
                    {hasFreeable
                      ? `You could free up about ${fmt(freeable, CURRENCY)} a month`
                      : "A few calm ways to save and grow"}
                  </div>
                  <div
                    className="text-sm leading-relaxed"
                    style={{ color: "rgba(255,255,255,.85)" }}
                  >
                    Here are a few calm, specific moves based on what Ledger found in
                    your inbox.
                  </div>
                </div>
                {hasFreeable && (
                  <span className="font-mono text-[32px] font-bold">
                    {fmt(freeable, CURRENCY)}
                  </span>
                )}
              </div>

              {/* Advice cards */}
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
                {cards.map((c) => (
                  <Card key={c.key} className="flex flex-col gap-3 p-5.5">
                    <div className="flex items-center gap-3">
                      <span
                        className="flex h-[42px] w-[42px] flex-none items-center justify-center rounded-[12px]"
                        style={{
                          background: accentTint(c.accent),
                          color: accent(c.accent),
                        }}
                      >
                        <Icon name={c.icon} size={20} />
                      </span>
                      <TagPill accent={c.accent}>{c.tag}</TagPill>
                    </div>
                    <div className="font-display font-semibold text-ink-900">
                      {c.title}
                    </div>
                    <div className="text-ink-600 leading-relaxed">{c.body}</div>
                  </Card>
                ))}
              </div>

              {/* Principles */}
              {(principles.length > 0 || advice?.disclaimer) && (
                <Card className="flex flex-col gap-4 p-6">
                  {principles.length > 0 && (
                    <>
                      <div className="font-display text-[17px] font-bold text-ink-900">
                        Principles
                      </div>
                      <ul className="flex flex-col gap-2.5">
                        {principles.map((p, i) => (
                          <li key={i} className="flex items-start gap-2.5">
                            <span
                              className="mt-0.5 flex-none"
                              style={{ color: "var(--violet-600)" }}
                            >
                              <Icon name="check" size={17} />
                            </span>
                            <span className="text-sm leading-relaxed text-ink-600">
                              {p}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                  {advice?.disclaimer && (
                    <div className="text-xs leading-relaxed text-ink-400">
                      {advice.disclaimer}
                    </div>
                  )}
                </Card>
              )}
            </div>
          )}
        </PageState>
      </div>
    </>
  );
}
