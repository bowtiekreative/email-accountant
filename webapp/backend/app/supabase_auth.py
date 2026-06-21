"""Verify Supabase-issued access tokens (JWTs) on the backend.

The frontend signs users in with Supabase Auth (Google / email+password) and
sends the resulting access token as `Authorization: Bearer <jwt>`. Here we
verify that token against the project's published signing keys (JWKS), so the
API trusts only tokens minted by *your* Supabase project.

Config (env):
  SUPABASE_JWKS_URL   e.g. https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
  SUPABASE_URL        e.g. https://<ref>.supabase.co  (used to derive issuer/JWKS)

Asymmetric keys (RS256/ES256 via JWKS) are preferred. As a fallback, a legacy
shared secret (SUPABASE_JWT_SECRET, HS256) is also supported.
"""

import os
from functools import lru_cache
from typing import Optional

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_JWKS_URL = os.environ.get("SUPABASE_JWKS_URL") or (
    f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else ""
)
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")  # legacy HS256 fallback
_ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else None
_AUDIENCE = "authenticated"


def supabase_auth_enabled() -> bool:
    """True when the backend is configured to trust Supabase tokens."""
    return bool(SUPABASE_JWKS_URL or SUPABASE_JWT_SECRET)


@lru_cache(maxsize=1)
def _jwk_client():
    from jwt import PyJWKClient

    # Cache JWKS for an hour; PyJWKClient refreshes on unknown kid.
    return PyJWKClient(SUPABASE_JWKS_URL, cache_keys=True, lifespan=3600)


def verify_supabase_token(token: Optional[str]) -> Optional[dict]:
    """Return the JWT claims if the token is a valid Supabase access token, else None."""
    if not token or not supabase_auth_enabled():
        return None
    try:
        import jwt
    except ImportError:
        return None

    opts = {"verify_aud": True}
    try:
        if SUPABASE_JWKS_URL:
            signing_key = _jwk_client().get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=_AUDIENCE,
                options=opts,
            )
        else:
            claims = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=_AUDIENCE,
                options=opts,
            )
        return claims
    except Exception:
        return None


def user_from_token(token: Optional[str]) -> Optional[str]:
    """Return a stable user identifier (email, else subject) from a valid token."""
    claims = verify_supabase_token(token)
    if not claims:
        return None
    return claims.get("email") or claims.get("sub")
