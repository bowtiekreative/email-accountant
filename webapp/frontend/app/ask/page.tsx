"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Icon } from "@/lib/ui";

type Msg = { role: "user" | "assistant"; content: string };

const GREETING: Msg = {
  role: "assistant",
  content:
    "Hi! I'm your Ledger assistant. Ask me anything about your spending — budgets, categories, what's tax-deductible, or a quick summary of the month.",
};

const SUGGESTIONS = [
  "Summarize my June spending",
  "Am I over budget anywhere?",
  "What can I deduct on taxes?",
  "How much on software?",
];

function Sparkle() {
  return (
    <span
      className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-[9px]"
      style={{ background: "var(--violet-100)", color: "var(--violet-600)" }}
    >
      <Icon name="sparkle" size={17} />
    </span>
  );
}

export default function AskPage() {
  const [messages, setMessages] = useState<Msg[]>([GREETING]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy) return;
    setInput("");
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next);
    setBusy(true);
    try {
      // Send the full conversation (drop the seeded greeting).
      const convo = next.filter((m) => m !== GREETING);
      const { reply } = await api.assistant(convo, "USD");
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            "Ask AI isn't available right now. Make sure an Anthropic API key is set on the backend.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Ask AI" subtitle="Ask anything about your spending" />
      <div className="px-8 py-7 pb-16 lg-fade-up h-full">
        <div className="mx-auto flex h-full max-w-[760px] flex-col gap-4">
          {/* Message list */}
          <div
            ref={scrollRef}
            className="flex flex-1 flex-col gap-4 overflow-y-auto pb-1.5"
          >
            {messages.map((m, i) =>
              m.role === "assistant" ? (
                <div key={i} className="flex items-start gap-[11px]">
                  <Sparkle />
                  <div className="whitespace-pre-wrap rounded-[14px] rounded-tl-[4px] border border-line bg-surface p-[14px_16px] text-[14.5px] leading-relaxed text-ink-700">
                    {m.content}
                  </div>
                </div>
              ) : (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[80%] whitespace-pre-wrap rounded-[14px] rounded-tr-[4px] bg-violet-600 p-[14px_16px] text-[14.5px] leading-relaxed text-white">
                    {m.content}
                  </div>
                </div>
              )
            )}

            {busy && (
              <div className="flex items-start gap-[11px]">
                <Sparkle />
                <div className="flex gap-[5px] rounded-[14px] rounded-tl-[4px] border border-line bg-surface p-[14px_16px]">
                  {[0, 0.2, 0.4].map((d) => (
                    <span
                      key={d}
                      className="h-[7px] w-[7px] rounded-pill"
                      style={{
                        background: "var(--ink-300)",
                        animation: `lg-blink 1s infinite ${d}s`,
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Suggestion chips */}
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                disabled={busy}
                className="whitespace-nowrap rounded-pill border border-line-strong bg-surface px-3.5 py-2 text-[13px] font-medium text-ink-700 transition-colors hover:border-violet-100 hover:bg-violet-50 hover:text-violet-700 disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>

          {/* Input bar */}
          <div className="flex items-center gap-2.5 rounded-[14px] border-[1.5px] border-line-strong bg-surface py-2 pl-4 pr-2 focus-within:border-violet-500">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Ask about your spending…"
              className="min-w-0 flex-1 border-none bg-transparent text-[15px] text-ink-900 outline-none placeholder:text-ink-400"
            />
            <button
              aria-label="Send"
              onClick={() => send(input)}
              disabled={busy || !input.trim()}
              className="flex h-10 w-10 flex-none items-center justify-center rounded-[10px] bg-violet-600 text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
            >
              <Icon name="send" size={18} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
