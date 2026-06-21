"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getSupabase, supabaseConfigured } from "@/lib/supabase";
import { Button, Icon, Spinner } from "@/lib/ui";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      if (supabaseConfigured) {
        const sb = getSupabase();
        if (mode === "signup") {
          const { error } = await sb.auth.signUp({ email, password });
          if (error) throw error;
          setInfo("Check your email to confirm your account, then sign in.");
          setMode("signin");
        } else {
          const { error } = await sb.auth.signInWithPassword({ email, password });
          if (error) throw error;
          router.replace("/");
        }
      } else {
        // Legacy username/password
        await api.login(email, password, remember);
        router.replace("/");
      }
    } catch (err: any) {
      setError(err.message || "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  async function google() {
    setError("");
    if (!supabaseConfigured) {
      setError("Google sign-in requires Supabase to be configured.");
      return;
    }
    const { error } = await getSupabase().auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: typeof window !== "undefined" ? window.location.origin : undefined },
    });
    if (error) setError(error.message);
  }

  return (
    <div className="flex h-screen w-full">
      {/* Left brand panel */}
      <div
        className="relative hidden flex-1 flex-col justify-between overflow-hidden p-12 text-white md:flex"
        style={{ background: "linear-gradient(155deg,var(--violet-600),var(--violet-700) 70%,#3a219c)" }}
      >
        <div className="absolute -right-20 -top-[90px] h-[340px] w-[340px] rounded-pill" style={{ background: "rgba(255,255,255,.08)" }} />
        <div className="absolute -bottom-[70px] -left-[50px] h-[240px] w-[240px] rounded-pill" style={{ background: "rgba(255,255,255,.06)" }} />
        <div className="relative flex items-center gap-[11px]">
          <div className="flex h-10 w-10 items-center justify-center rounded-[11px]" style={{ background: "rgba(255,255,255,.18)" }}>
            <Icon name="mail" size={21} />
          </div>
          <span className="font-display text-[19px] font-bold">Ledger</span>
        </div>

        <div className="relative max-w-[420px]">
          <div className="mb-[34px] flex gap-3.5">
            <ReceiptCard rotate={-7} bar="var(--coral-500)" amount="$84.20" top={0} />
            <ReceiptCard rotate={5} bar="var(--teal-500)" amount="$15.00" top={18} />
          </div>
          <h2 className="m-0 mb-3 font-display text-[30px] font-bold leading-tight tracking-[-0.02em]">
            Let your inbox do the bookkeeping.
          </h2>
          <p className="m-0 text-[15px] leading-relaxed" style={{ color: "rgba(255,255,255,.82)" }}>
            Ledger scans your email for receipts and invoices, then sorts every expense for you — calm, clear, and made for every kind of brain.
          </p>
        </div>

        <span className="relative text-[12.5px]" style={{ color: "rgba(255,255,255,.6)" }}>
          A Bow Tie Kreative product
        </span>
      </div>

      {/* Right form */}
      <div className="flex w-full flex-none items-center justify-center bg-surface p-10 md:w-[480px] md:max-w-[48vw]">
        <form onSubmit={submit} className="flex w-full max-w-[340px] flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <h1 className="m-0 font-display text-[26px] font-bold tracking-[-0.02em] text-ink-900">
              {mode === "signin" ? "Welcome back" : "Create your account"}
            </h1>
            <span className="text-sm text-ink-500">
              {mode === "signin" ? "Sign in to see your receipts." : "Start letting your inbox do the bookkeeping."}
            </span>
          </div>

          {supabaseConfigured && (
            <>
              <button
                type="button"
                onClick={google}
                className="flex h-[46px] items-center justify-center gap-2.5 rounded-[11px] border border-line-strong bg-surface font-body text-[14.5px] font-semibold text-ink-800 hover:bg-surface-sunken"
              >
                <GoogleMark />
                Continue with Google
              </button>
              <div className="flex items-center gap-3 text-ink-300">
                <span className="h-px flex-1 bg-line" />
                <span className="text-xs">or</span>
                <span className="h-px flex-1 bg-line" />
              </div>
            </>
          )}

          <label className="flex flex-col gap-[7px]">
            <span className="text-[12.5px] font-semibold text-ink-700">
              {supabaseConfigured ? "Email" : "Username"}
            </span>
            <input
              autoFocus
              type={supabaseConfigured ? "email" : "text"}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-[11px] border-[1.5px] border-line-strong bg-surface px-3.5 py-3 font-body text-[15px] text-ink-900 outline-none focus:border-violet-500"
            />
          </label>
          <label className="flex flex-col gap-[7px]">
            <span className="text-[12.5px] font-semibold text-ink-700">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-[11px] border-[1.5px] border-line-strong bg-surface px-3.5 py-3 font-body text-[15px] text-ink-900 outline-none focus:border-violet-500"
            />
          </label>

          {!supabaseConfigured && (
            <label className="flex cursor-pointer items-center gap-2 text-[13px] text-ink-600">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                style={{ width: 16, height: 16, accentColor: "var(--violet-600)" }}
              />
              Remember me
            </label>
          )}

          {error && <p className="m-0 text-sm text-danger-600">{error}</p>}
          {info && <p className="m-0 text-sm text-success-600">{info}</p>}

          <Button type="submit" size="lg" block disabled={busy}>
            {busy ? <Spinner light /> : mode === "signin" ? "Sign in" : "Create account"}
          </Button>

          {supabaseConfigured && (
            <span className="text-center text-[13.5px] text-ink-500">
              {mode === "signin" ? "New here? " : "Already have an account? "}
              <button
                type="button"
                onClick={() => {
                  setMode(mode === "signin" ? "signup" : "signin");
                  setError("");
                  setInfo("");
                }}
                className="font-semibold text-violet-600"
              >
                {mode === "signin" ? "Create an account" : "Sign in"}
              </button>
            </span>
          )}
        </form>
      </div>
    </div>
  );
}

function ReceiptCard({ rotate, bar, amount, top }: { rotate: number; bar: string; amount: string; top: number }) {
  return (
    <div
      className="h-[150px] w-[120px] rounded-xl bg-white p-3.5"
      style={{ transform: `rotate(${rotate}deg)`, boxShadow: "0 20px 40px -16px rgba(0,0,0,.4)", marginTop: top }}
    >
      <div className="mb-3 h-1 w-3/5 rounded-pill" style={{ background: bar }} />
      <div className="mb-2 h-[5px] w-[90%] rounded-pill bg-[#eee]" />
      <div className="mb-2 h-[5px] w-[70%] rounded-pill bg-[#eee]" />
      <div className="h-[5px] w-[80%] rounded-pill bg-[#eee]" />
      <div className="mt-[30px] font-mono text-[15px] font-bold text-ink-900">{amount}</div>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}
