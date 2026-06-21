import type { Metadata } from "next";
import "./globals.css";
import AuthGate from "@/components/AuthGate";

export const metadata: Metadata = {
  title: "Ledger — by Bow Tie Kreative",
  description:
    "Ledger lets your inbox do the bookkeeping — it scans your email for receipts and invoices, then sorts every expense for you.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthGate>{children}</AuthGate>
      </body>
    </html>
  );
}
