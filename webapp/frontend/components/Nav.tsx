"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api, clearCache } from "@/lib/api";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/transactions", label: "Transactions" },
  { href: "/review", label: "Review" },
  { href: "/planning", label: "Planning" },
  { href: "/invest", label: "Invest" },
  { href: "/tax", label: "Tax" },
  { href: "/scans", label: "Scans" },
  { href: "/accounts", label: "Accounts" },
  { href: "/connections", label: "Connections" },
];

export default function Nav() {
  const path = usePathname();
  const router = useRouter();

  function logout() {
    api.logout();
    router.replace("/login");
  }

  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-1 px-4">
        <span className="mr-4 py-4 text-lg font-bold text-ink">
          📬 Email Accountant
        </span>
        {links.map((l) => {
          const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`px-3 py-4 text-sm font-medium transition ${
                active
                  ? "border-b-2 border-accent text-ink"
                  : "text-slate-500 hover:text-ink"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => clearCache()}
            title="Clear cached data and reload"
            className="px-3 py-4 text-sm font-medium text-slate-500 hover:text-ink"
          >
            Clear cache
          </button>
          <Link
            href="/account"
            className={`px-3 py-4 text-sm font-medium transition ${
              path.startsWith("/account")
                ? "border-b-2 border-accent text-ink"
                : "text-slate-500 hover:text-ink"
            }`}
          >
            Account
          </Link>
          <button
            onClick={logout}
            className="px-3 py-4 text-sm font-medium text-rose-600 hover:text-rose-700"
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
