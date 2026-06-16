"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/transactions", label: "Transactions" },
  { href: "/review", label: "Review" },
  { href: "/tax", label: "Tax / Schedule C" },
  { href: "/scans", label: "Scans" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-1 px-4">
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
      </div>
    </nav>
  );
}
