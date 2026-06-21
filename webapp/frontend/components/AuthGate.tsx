"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";
import { getSupabase, supabaseConfigured } from "@/lib/supabase";
import Shell from "@/components/Shell";
import { Spinner } from "@/lib/ui";

/**
 * Gates the app behind authentication. With Supabase configured this checks the
 * Supabase session (and reacts to sign-in/out); otherwise it falls back to the
 * legacy signed-token flow. The /login route renders bare (no sidebar).
 */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  const onLogin = pathname === "/login";

  useEffect(() => {
    let unsub: (() => void) | undefined;

    async function check() {
      if (supabaseConfigured) {
        const { data } = await getSupabase().auth.getSession();
        const ok = Boolean(data.session);
        setAuthed(ok);
        setReady(true);
        if (!ok && !onLogin) router.replace("/login");
        const sub = getSupabase().auth.onAuthStateChange((_e, session) => {
          setAuthed(Boolean(session));
          if (!session && !onLogin) router.replace("/login");
        });
        unsub = () => sub.data.subscription.unsubscribe();
        return;
      }
      // Legacy token flow
      if (!getToken()) {
        setReady(true);
        if (!onLogin) router.replace("/login");
        return;
      }
      try {
        await api.me();
        setAuthed(true);
      } catch {
        if (!onLogin) router.replace("/login");
      } finally {
        setReady(true);
      }
    }

    check();
    return () => unsub?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (onLogin) return <>{children}</>;

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center gap-3 text-ink-400">
        <Spinner /> <span className="text-sm">Loading Ledger…</span>
      </div>
    );
  }
  if (!authed) {
    return (
      <div className="flex h-screen items-center justify-center text-ink-400">
        <Spinner />
      </div>
    );
  }
  return <Shell>{children}</Shell>;
}
