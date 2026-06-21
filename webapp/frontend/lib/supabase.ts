"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Browser Supabase client. Uses the *publishable* key (safe to ship to the
 * browser) — never the secret key. Configure these in webapp/frontend/.env.local:
 *
 *   NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
 *   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
 *
 * The backend independently verifies the access token via SUPABASE_JWKS_URL.
 */
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const publishableKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
  "";

/** True when the app is configured for Supabase auth. */
export const supabaseConfigured = Boolean(url && publishableKey);

let _client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!supabaseConfigured) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and " +
        "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY in webapp/frontend/.env.local."
    );
  }
  if (!_client) {
    _client = createClient(url, publishableKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return _client;
}

/** Current Supabase access token (JWT) for Authorization: Bearer, or null. */
export async function getAccessToken(): Promise<string | null> {
  if (!supabaseConfigured) return null;
  const { data } = await getSupabase().auth.getSession();
  return data.session?.access_token ?? null;
}
