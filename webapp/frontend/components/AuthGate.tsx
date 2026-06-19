"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";

/**
 * Gates the whole app behind login. Unauthenticated users are sent to /login;
 * the login page renders without the nav. Verifies the token on load.
 */
export default function AuthGate({
  children,
  nav,
}: {
  children: React.ReactNode;
  nav: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  const onLogin = pathname === "/login";

  useEffect(() => {
    if (onLogin) {
      setReady(true);
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    // Validate the token; a 401 clears it and redirects via the api layer.
    api
      .me()
      .then(() => setReady(true))
      .catch(() => router.replace("/login"));
  }, [pathname, onLogin, router]);

  if (onLogin) {
    return <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>;
  }
  if (!ready) {
    return <div className="p-10 text-center text-slate-400">Loading…</div>;
  }
  return (
    <>
      {nav}
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </>
  );
}
