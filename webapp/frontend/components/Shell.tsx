"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getSupabase, supabaseConfigured } from "@/lib/supabase";
import { Icon, type IconName } from "@/lib/ui";

const NAV: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Gallery", icon: "grid" },
  { href: "/transactions", label: "Transactions", icon: "list" },
  { href: "/insights", label: "Insights", icon: "bars" },
  { href: "/categories", label: "Categories", icon: "tag" },
  { href: "/investments", label: "Investments", icon: "trending" },
  { href: "/advice", label: "Advice", icon: "bulb" },
  { href: "/ask", label: "Ask AI", icon: "chat" },
  { href: "/reports", label: "Reports", icon: "file" },
  { href: "/settings", label: "Settings", icon: "gear" },
];

function initials(nameOrEmail: string): string {
  const base = nameOrEmail.includes("@") ? nameOrEmail.split("@")[0] : nameOrEmail;
  const parts = base.replace(/[._-]+/g, " ").trim().split(/\s+/);
  return (parts[0]?.[0] || "?").concat(parts[1]?.[0] || "").toUpperCase();
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<{ name: string; email: string }>({ name: "", email: "" });
  const [accounts, setAccounts] = useState<{ active: boolean }[] | null>(null);

  useEffect(() => {
    (async () => {
      if (supabaseConfigured) {
        const { data } = await getSupabase().auth.getUser();
        const u = data.user;
        if (u) {
          const name = (u.user_metadata?.full_name as string) || (u.user_metadata?.name as string) || "";
          setUser({ name, email: u.email || "" });
        }
      } else {
        try {
          const me = await api.me();
          setUser({ name: me.username, email: me.email || "" });
        } catch {
          /* ignore */
        }
      }
    })();
    api.accounts().then(setAccounts).catch(() => setAccounts([]));
  }, []);

  async function logout() {
    await api.logout();
    router.replace("/login");
  }

  const activeAccounts = accounts?.filter((a) => a.active).length ?? 0;
  const connected = activeAccounts > 0;

  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <div className="flex h-screen w-full overflow-hidden bg-canvas">
      {/* Sidebar */}
      <aside className="flex w-[248px] flex-none flex-col border-r border-line bg-surface px-4 py-[22px]">
        <div className="flex items-center gap-[11px] px-2 pb-5">
          <div
            className="flex h-[38px] w-[38px] items-center justify-center rounded-[11px] text-white"
            style={{
              background: "linear-gradient(140deg,var(--violet-500),var(--violet-700))",
              boxShadow: "0 4px 14px -4px rgba(100,66,238,.55)",
            }}
          >
            <Icon name="mail" size={20} />
          </div>
          <div className="flex flex-col leading-[1.1]">
            <span className="font-display text-base font-bold tracking-[-0.01em] text-ink-900">Ledger</span>
            <span className="text-[11px] text-ink-500">by Bow Tie Kreative</span>
          </div>
        </div>

        <nav className="flex flex-col gap-0.5 overflow-y-auto">
          {NAV.map((n) => {
            const active = isActive(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`flex items-center gap-3 rounded-sm px-3 py-2.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-violet-50 text-violet-700"
                    : "text-ink-600 hover:bg-surface-sunken hover:text-ink-900"
                }`}
              >
                <Icon name={n.icon} size={18} />
                {n.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto flex flex-col gap-3 pt-3.5">
          <Link
            href="/settings"
            className="flex flex-col gap-2 rounded-[14px] border p-[13px_14px] transition-colors"
            style={{
              background: connected ? "var(--teal-50)" : "var(--amber-50)",
              borderColor: connected ? "var(--teal-100)" : "var(--amber-100)",
            }}
          >
            <div className="flex items-center gap-2">
              <span
                className="h-2 w-2 rounded-pill"
                style={{
                  background: connected ? "var(--teal-600)" : "var(--amber-600)",
                  boxShadow: `0 0 0 3px ${connected ? "var(--teal-100)" : "var(--amber-100)"}`,
                }}
              />
              <span
                className="text-[12.5px] font-semibold"
                style={{ color: connected ? "var(--teal-700)" : "var(--amber-700)" }}
              >
                {connected ? "Gmail connected" : "Connect an inbox"}
              </span>
            </div>
            <span className="text-[11.5px] leading-snug text-ink-500">
              {accounts === null
                ? "Checking inbox status…"
                : connected
                ? `${activeAccounts} account${activeAccounts > 1 ? "s" : ""} · auto-scan on`
                : "Add an email account to start scanning"}
            </span>
          </Link>

          <div className="flex items-center gap-2.5 px-1 py-1">
            <div
              className="flex h-[34px] w-[34px] items-center justify-center rounded-pill font-display text-sm font-bold"
              style={{ background: "var(--coral-100)", color: "var(--coral-600)" }}
            >
              {initials(user.name || user.email || "?")}
            </div>
            <div className="flex min-w-0 flex-1 flex-col leading-tight">
              <span className="truncate text-[13px] font-semibold text-ink-900">
                {user.name || user.email || "Account"}
              </span>
              <span className="text-[11px] text-ink-500">Signed in</span>
            </div>
            <button
              aria-label="Sign out"
              onClick={logout}
              className="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-[8px] border border-line-strong bg-surface text-ink-500 hover:bg-surface-sunken hover:text-ink-700"
            >
              <Icon name="logout" size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">{children}</div>
      </main>
    </div>
  );
}
